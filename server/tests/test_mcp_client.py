"""MCP client/server round trips over in-process and stdio transports."""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

from agent.mcp_session import McpSession, McpToolError, default_stdio_parameters
from agent.models import ToolCall
from agent.tool_executor import ToolExecutor
from mcp_server.tools import TOOL_DEFINITIONS

EXPECTED_TOOLS = {item["name"] for item in TOOL_DEFINITIONS}


@pytest.fixture
async def inprocess_session() -> McpSession:
    session = McpSession()
    assert session.transport == "inprocess"
    await session.connect()
    yield session
    await session.close()


class TestInProcessRoundTrip:
    @pytest.mark.asyncio
    async def test_list_tools_matches_server_definitions(self, inprocess_session: McpSession):
        tools = await inprocess_session.list_tools()
        names = {tool["name"] for tool in tools}
        assert names == EXPECTED_TOOLS
        for tool in tools:
            assert tool["inputSchema"]["type"] == "object"
            assert "description" in tool

    @pytest.mark.asyncio
    async def test_call_tool_list_cities(self, inprocess_session: McpSession):
        text = await inprocess_session.call_tool("list_available_cities", {})
        payload = json.loads(text)
        assert payload["count"] == 10
        assert "Sydney" in payload["available_cities"]

    @pytest.mark.asyncio
    async def test_call_tool_validation_error(self, inprocess_session: McpSession):
        with pytest.raises(McpToolError, match="city parameter is required"):
            await inprocess_session.call_tool("get_current_weather", {"city": ""})

    @respx.mock
    @pytest.mark.asyncio
    async def test_call_tool_current_weather(self, inprocess_session: McpSession):
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(
                200,
                json={
                    "current": {
                        "time": "2024-10-06T10:00",
                        "temperature_2m": 22.5,
                        "relative_humidity_2m": 65,
                        "apparent_temperature": 21.0,
                        "is_day": 1,
                        "precipitation": 0.0,
                        "weather_code": 1,
                        "wind_speed_10m": 15.0,
                        "wind_direction_10m": 180,
                    }
                },
            )
        )
        text = await inprocess_session.call_tool("get_current_weather", {"city": "Sydney"})
        payload = json.loads(text)
        assert payload["city"] == "Sydney"
        assert payload["temperature_celsius"] == 22.5


class TestStdioRoundTrip:
    @pytest.mark.asyncio
    async def test_stdio_list_tools_and_list_cities(self):
        session = McpSession(default_stdio_parameters())
        assert session.transport == "stdio"
        try:
            tools = await session.list_tools()
            assert {tool["name"] for tool in tools} == EXPECTED_TOOLS
            text = await session.call_tool("list_available_cities", {})
            payload = json.loads(text)
            assert payload["count"] == 10
            assert "Sydney" in payload["available_cities"]
        finally:
            await session.close()


class TestToolExecutorRetries:
    @pytest.mark.asyncio
    async def test_retries_open_meteo_errors_then_succeeds(self):
        class FlakySession:
            transport = "inprocess"

            def __init__(self) -> None:
                self.calls = 0

            async def list_tools(self):
                return []

            async def call_tool(self, name: str, arguments: dict | None = None) -> str:
                self.calls += 1
                if self.calls < 3:
                    raise McpToolError("Error: Open-Meteo request failed: timeout")
                return '{"city": "Sydney"}'

        session = FlakySession()
        executor = ToolExecutor(session)  # type: ignore[arg-type]
        result = await executor.execute(
            ToolCall(id="c1", name="get_current_weather", arguments={"city": "Sydney"})
        )
        assert result.success is True
        assert session.calls == 3

    @pytest.mark.asyncio
    async def test_does_not_retry_validation_errors(self):
        class OnceSession:
            transport = "inprocess"
            calls = 0

            async def call_tool(self, name: str, arguments: dict | None = None) -> str:
                self.calls += 1
                raise McpToolError("Error: city parameter is required")

        session = OnceSession()
        executor = ToolExecutor(session)  # type: ignore[arg-type]
        result = await executor.execute(
            ToolCall(id="c1", name="get_current_weather", arguments={"city": ""})
        )
        assert result.success is False
        assert session.calls == 1
        assert "city parameter is required" in result.result
