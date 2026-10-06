"""Main agent implementation with planning, tool calling, and guardrails."""

import os
from typing import Any

from .demo_client import DemoLLMClient
from .guardrails import Guardrails
from .llm_client import LLMClient, create_llm_client
from .mcp_session import McpSession
from .models import ConversationState, MessageRole, TraceEventType
from .tool_executor import ToolExecutor


class Agent:
    """AI Agent with tool-using capabilities, planning, and guardrails."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        demo_mode: bool = False,
        mcp_session: McpSession | None = None,
    ) -> None:
        self.demo_mode = demo_mode or os.getenv("DEMO_MODE", "").lower() == "true"
        self.llm_client: LLMClient

        if llm_client is not None:
            self.llm_client = llm_client
        elif self.demo_mode:
            self.llm_client = DemoLLMClient()
        else:
            try:
                self.llm_client = create_llm_client()
            except ValueError:
                self.demo_mode = True
                self.llm_client = DemoLLMClient()

        self._owns_mcp_session = mcp_session is None
        self.mcp_session = mcp_session or McpSession()
        self.tool_executor = ToolExecutor(self.mcp_session)
        self.guardrails = Guardrails()
        self.max_iterations = 10

    async def chat(
        self,
        user_message: str,
        conversation: ConversationState | None = None,
    ) -> tuple[str, ConversationState]:
        """Process a user message and return the response with updated state."""
        if conversation is None:
            conversation = ConversationState()

        input_check = self.guardrails.check_input(user_message)
        if not input_check.passed:
            conversation.add_trace(
                TraceEventType.GUARDRAIL,
                f"Input blocked: {input_check.message}",
                input_check.details,
            )
            return input_check.message, conversation

        turn_check = self.guardrails.check_conversation_length(len(conversation.messages) // 2)
        if not turn_check.passed:
            conversation.add_trace(
                TraceEventType.GUARDRAIL,
                f"Conversation limit: {turn_check.message}",
                turn_check.details,
            )
            return turn_check.message, conversation

        conversation.add_message(MessageRole.USER, user_message)
        preview = user_message if len(user_message) <= 100 else f"{user_message[:100]}..."
        conversation.add_trace(
            TraceEventType.PLANNING,
            f"Received user message: {preview}",
            {"message_length": len(user_message)},
        )

        messages = self._build_messages(conversation)
        tools = await self.tool_executor.get_tools()
        conversation.add_trace(
            TraceEventType.PLANNING,
            (f"MCP tools/list: discovered {len(tools)} tools over {self.mcp_session.transport}"),
            {
                "protocol": "mcp",
                "method": "tools/list",
                "transport": self.mcp_session.transport,
                "tools": [tool["name"] for tool in tools],
            },
        )

        final_response = ""
        iterations = 0

        while iterations < self.max_iterations:
            iterations += 1

            conversation.add_trace(
                TraceEventType.THINKING,
                f"Iteration {iterations}: Generating response",
                {"iteration": iterations},
            )

            try:
                response = await self.llm_client.generate(messages, tools)
            except Exception as exc:
                conversation.add_trace(
                    TraceEventType.ERROR,
                    f"Error generating response: {exc}",
                    {"error_type": type(exc).__name__},
                )
                return f"I encountered an error: {exc}", conversation

            if response.content:
                final_response = response.content

            if not response.tool_calls:
                break

            tool_check = self.guardrails.check_tool_calls(
                [tc.to_dict() for tc in response.tool_calls],
                iterations,
            )
            if not tool_check.passed:
                conversation.add_trace(
                    TraceEventType.GUARDRAIL,
                    f"Tool calls blocked: {tool_check.message}",
                    tool_check.details,
                )
                break

            for tool_call in response.tool_calls:
                arg_check = self.guardrails.check_tool_arguments(
                    tool_call.name, tool_call.arguments
                )
                if not arg_check.passed:
                    conversation.add_trace(
                        TraceEventType.GUARDRAIL,
                        f"Tool arguments blocked: {arg_check.message}",
                        {"tool": tool_call.name},
                    )
                    continue

                conversation.add_trace(
                    TraceEventType.TOOL_CALL,
                    f"MCP tools/call {tool_call.name}",
                    {
                        "protocol": "mcp",
                        "method": "tools/call",
                        "transport": self.mcp_session.transport,
                        "tool": tool_call.name,
                        "arguments": tool_call.arguments,
                    },
                )

                result = await self.tool_executor.execute(tool_call)
                conversation.tool_results.append(result)

                if result.success:
                    conversation.add_trace(
                        TraceEventType.TOOL_RESULT,
                        (
                            f"MCP tools/call {tool_call.name} completed "
                            f"in {result.duration_ms:.0f}ms"
                        ),
                        {
                            "protocol": "mcp",
                            "method": "tools/call",
                            "transport": self.mcp_session.transport,
                            "tool": tool_call.name,
                            "success": True,
                            "duration_ms": result.duration_ms,
                        },
                    )
                else:
                    conversation.add_trace(
                        TraceEventType.RETRY,
                        f"MCP tools/call {tool_call.name} failed: {result.result}",
                        {
                            "protocol": "mcp",
                            "method": "tools/call",
                            "transport": self.mcp_session.transport,
                            "tool": tool_call.name,
                            "success": False,
                        },
                    )

                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.name,
                                    "arguments": str(tool_call.arguments),
                                },
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result.result,
                    }
                )

        response_check = self.guardrails.check_response(final_response)
        if not response_check.passed:
            final_response = (
                "I generated a response that was too long. Please try a more specific question."
            )
            conversation.add_trace(
                TraceEventType.GUARDRAIL,
                "Response truncated",
                response_check.details,
            )

        conversation.add_message(MessageRole.ASSISTANT, final_response)
        return final_response, conversation

    def _build_messages(self, conversation: ConversationState) -> list[dict[str, Any]]:
        """Build message list for LLM from conversation state."""
        return [{"role": msg.role.value, "content": msg.content} for msg in conversation.messages]

    async def close(self) -> None:
        """Clean up resources owned by this agent."""
        await self.tool_executor.close()
        if self._owns_mcp_session:
            await self.mcp_session.close()
