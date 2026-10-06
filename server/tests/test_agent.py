"""Tests for the agent."""

from unittest.mock import MagicMock

import pytest

from agent.agent import Agent
from agent.llm_client import LLMClient
from agent.mcp_session import McpSession
from agent.models import AgentResponse, ConversationState, MessageRole, ToolCall, TraceEventType


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(self, responses: list[AgentResponse]):
        self.responses = responses
        self.call_count = 0

    async def generate(self, messages, tools=None):
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        return AgentResponse(content="No more responses", tool_calls=[])


@pytest.fixture
def simple_response():
    return AgentResponse(
        content="The weather in Sydney is sunny with 25°C.",
        tool_calls=[],
        finish_reason="stop",
    )


@pytest.fixture
def tool_call_response():
    return AgentResponse(
        content="",
        tool_calls=[
            ToolCall(
                id="call_1",
                name="get_current_weather",
                arguments={"city": "Sydney"},
            )
        ],
        finish_reason="tool_calls",
    )


@pytest.fixture
async def agent_session() -> McpSession:
    session = McpSession()
    yield session
    await session.close()


class TestAgent:
    @pytest.mark.asyncio
    async def test_simple_chat(self, simple_response, agent_session):
        mock_client = MockLLMClient([simple_response])
        agent = Agent(llm_client=mock_client, mcp_session=agent_session)

        response, conversation = await agent.chat("What's the weather?")

        assert "weather" in response.lower() or "Sydney" in response
        assert len(conversation.messages) == 2
        assert conversation.messages[0].role == MessageRole.USER
        assert conversation.messages[1].role == MessageRole.ASSISTANT

    @pytest.mark.asyncio
    async def test_conversation_state_tracking(self, simple_response, agent_session):
        mock_client = MockLLMClient([simple_response])
        agent = Agent(llm_client=mock_client, mcp_session=agent_session)

        _, conversation = await agent.chat("Hello")

        assert len(conversation.trace) > 0
        trace_types = [t.type for t in conversation.trace]
        assert TraceEventType.PLANNING in trace_types
        assert TraceEventType.THINKING in trace_types
        assert any("MCP tools/list" in event.content for event in conversation.trace)

    @pytest.mark.asyncio
    async def test_tool_execution(self, tool_call_response, simple_response, agent_session):
        mock_client = MockLLMClient([tool_call_response, simple_response])
        agent = Agent(llm_client=mock_client, mcp_session=agent_session)

        _response, conversation = await agent.chat("What's the weather in Sydney?")

        assert len(conversation.tool_results) > 0
        trace_types = [t.type for t in conversation.trace]
        assert TraceEventType.TOOL_CALL in trace_types
        assert TraceEventType.TOOL_RESULT in trace_types
        tool_events = [
            event for event in conversation.trace if event.type == TraceEventType.TOOL_CALL
        ]
        assert tool_events[0].content.startswith("MCP tools/call")
        assert tool_events[0].metadata["protocol"] == "mcp"
        assert tool_events[0].metadata["method"] == "tools/call"
        assert tool_events[0].metadata["transport"] == "inprocess"

    @pytest.mark.asyncio
    async def test_guardrail_input_length(self, agent_session):
        agent = Agent(demo_mode=True, mcp_session=agent_session)

        long_input = "a" * 3000  # Exceeds MAX_INPUT_LENGTH
        response, conversation = await agent.chat(long_input)

        assert "too long" in response.lower()
        trace_types = [t.type for t in conversation.trace]
        assert TraceEventType.GUARDRAIL in trace_types

    @pytest.mark.asyncio
    async def test_conversation_continuity(self, simple_response, agent_session):
        mock_client = MockLLMClient([simple_response, simple_response])
        agent = Agent(llm_client=mock_client, mcp_session=agent_session)

        _, conversation1 = await agent.chat("First message")
        _, conversation2 = await agent.chat("Second message", conversation1)

        assert len(conversation2.messages) == 4  # 2 user + 2 assistant

    @pytest.mark.asyncio
    async def test_demo_mode(self, agent_session):
        agent = Agent(demo_mode=True, mcp_session=agent_session)

        response, conversation = await agent.chat("What's the weather in Sydney?")

        assert len(response) > 0
        assert agent.demo_mode is True
        assert any(event.metadata.get("method") == "tools/call" for event in conversation.trace)

    @pytest.mark.asyncio
    async def test_demo_compare_is_not_treated_as_single_city_weather(self, agent_session):
        agent = Agent(demo_mode=True, mcp_session=agent_session)

        response, conversation = await agent.chat(
            "Compare weather in Sydney, Melbourne and Brisbane"
        )

        tool_names = [result.name for result in conversation.tool_results]
        assert "compare_cities_weather" in tool_names
        assert "Warmest" in response or "comparison" in response.lower()
        assert any(
            event.content.startswith("MCP tools/call compare_cities_weather")
            for event in conversation.trace
        )

    @pytest.mark.asyncio
    async def test_error_handling(self, agent_session):
        class FailingClient(LLMClient):
            async def generate(self, messages, tools=None):
                raise Exception("API Error")

        agent = Agent(llm_client=FailingClient(), mcp_session=agent_session)
        response, conversation = await agent.chat("Hello")

        assert "error" in response.lower()
        trace_types = [t.type for t in conversation.trace]
        assert TraceEventType.ERROR in trace_types


class TestGuardrails:
    @pytest.mark.asyncio
    async def test_conversation_turn_limit(self, agent_session):
        agent = Agent(demo_mode=True, mcp_session=agent_session)
        conversation = ConversationState()

        # Simulate many turns
        for i in range(25):
            conversation.messages.append(MagicMock(role=MessageRole.USER, content=f"Message {i}"))
            conversation.messages.append(
                MagicMock(role=MessageRole.ASSISTANT, content=f"Response {i}")
            )

        response, _ = await agent.chat("Another message", conversation)

        assert "too long" in response.lower() or "new conversation" in response.lower()


class TestConversationState:
    def test_add_message(self):
        state = ConversationState()
        state.add_message(MessageRole.USER, "Hello")

        assert len(state.messages) == 1
        assert state.messages[0].content == "Hello"
        assert state.messages[0].role == MessageRole.USER

    def test_add_trace(self):
        state = ConversationState()
        state.add_trace(TraceEventType.THINKING, "Processing...")

        assert len(state.trace) == 1
        assert state.trace[0].type == TraceEventType.THINKING
        assert state.trace[0].content == "Processing..."

    def test_to_dict(self):
        state = ConversationState()
        state.add_message(MessageRole.USER, "Hello")
        state.add_trace(TraceEventType.THINKING, "Processing...")

        result = state.to_dict()

        assert "messages" in result
        assert "trace" in result
        assert "tool_results" in result
        assert len(result["messages"]) == 1
        assert len(result["trace"]) == 1
