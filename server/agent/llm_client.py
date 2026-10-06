"""LLM client abstraction supporting multiple providers."""

import json
import os
from abc import ABC, abstractmethod
from typing import Any

from .models import AgentResponse, ToolCall

SYSTEM_PROMPT = """You are a helpful AI assistant with access to Australian weather data tools.

You can:
1. Get current weather for Australian cities
2. Get weather forecasts for up to 16 days
3. Compare weather across multiple cities
4. List available cities

When answering questions:
- Use tools to get accurate, real-time data
- Think step by step for complex questions
- If a question requires multiple pieces of information, call tools in sequence
- Provide clear, well-formatted responses with the data

Available cities: Sydney, Melbourne, Brisbane, Perth, Adelaide, Canberra, Hobart, Darwin, Gold Coast, Newcastle

Always be helpful and provide specific data from the tools rather than general statements."""


def _format_tools_for_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format MCP tools for OpenAI function calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
            },
        }
        for tool in tools
    ]


def _format_tools_for_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format MCP tools for Anthropic tool use."""
    return [
        {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool.get("inputSchema", {"type": "object", "properties": {}}),
        }
        for tool in tools
    ]


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AgentResponse:
        """Generate a response from the LLM."""
        pass


class OpenAIClient(LLMClient):
    """OpenAI API client."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AgentResponse:
        client = await self._get_client()

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        }

        if tools:
            kwargs["tools"] = _format_tools_for_openai(tools)
            kwargs["tool_choice"] = "auto"

        response = await client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        return AgentResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason or "stop",
        )


class AnthropicClient(LLMClient):
    """Anthropic API client."""

    def __init__(self, api_key: str | None = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AgentResponse:
        client = await self._get_client()

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }

        if tools:
            kwargs["tools"] = _format_tools_for_anthropic(tools)

        response = await client.messages.create(**kwargs)

        content_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        return AgentResponse(
            content="\n".join(content_parts),
            tool_calls=tool_calls,
            finish_reason=response.stop_reason or "stop",
        )


def create_llm_client(provider: str | None = None) -> LLMClient:
    """Create an LLM client based on available API keys."""
    provider = provider or os.getenv("LLM_PROVIDER", "").lower()

    if provider == "openai" or os.getenv("OPENAI_API_KEY"):
        return OpenAIClient()
    elif provider == "anthropic" or os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicClient()
    else:
        raise ValueError(
            "No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY, "
            "or use demo mode with DEMO_MODE=true"
        )
