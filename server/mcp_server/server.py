"""MCP stdio server for Australian weather tools (MCP Python SDK 2.x)."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer

from .tools import execute_weather_tool
from .weather_client import WeatherAPIError, WeatherClient

weather_client = WeatherClient()
mcp = MCPServer(
    name="trace-weather",
    instructions=(
        "Australian weather tools backed by Open-Meteo. "
        "Supported cities: Adelaide, Brisbane, Canberra, Darwin, Gold Coast, "
        "Hobart, Melbourne, Newcastle, Perth, Sydney."
    ),
)


def _format_result(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


async def _run_tool(name: str, arguments: dict[str, Any]) -> str:
    try:
        result = await execute_weather_tool(weather_client, name, arguments)
        return _format_result(result)
    except (ValueError, WeatherAPIError) as exc:
        return f"Error: {exc}"


@mcp.tool()
async def get_current_weather(city: str) -> str:
    """Get the current weather conditions for an Australian city."""
    return await _run_tool("get_current_weather", {"city": city})


@mcp.tool()
async def get_weather_forecast(city: str, days: int = 7) -> str:
    """Get a daily weather forecast for an Australian city (1-16 days)."""
    return await _run_tool("get_weather_forecast", {"city": city, "days": days})


@mcp.tool()
async def compare_cities_weather(cities: list[str]) -> str:
    """Compare current weather across up to five Australian cities."""
    return await _run_tool("compare_cities_weather", {"cities": cities})


@mcp.tool()
async def list_available_cities() -> str:
    """List Australian cities supported by this weather service."""
    return await _run_tool("list_available_cities", {})


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
