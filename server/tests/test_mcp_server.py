"""Tests for MCP 2 tool registration and shared execution."""

import json

import pytest
import respx
from httpx import Response

from mcp_server.server import (
    compare_cities_weather,
    get_current_weather,
    get_weather_forecast,
    list_available_cities,
    mcp,
)
from mcp_server.tools import TOOL_DEFINITIONS, execute_weather_tool
from mcp_server.weather_client import WeatherClient


@pytest.mark.asyncio
async def test_mcp_lists_the_same_tools_as_the_agent():
    tools = await mcp.list_tools()
    names = sorted(tool.name for tool in tools)
    assert names == sorted(item["name"] for item in TOOL_DEFINITIONS)
    for tool in tools:
        assert tool.input_schema["type"] == "object"


@respx.mock
@pytest.mark.asyncio
async def test_mcp_current_weather_tool_function():
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
    text = await get_current_weather("Sydney")
    payload = json.loads(text)
    assert payload["city"] == "Sydney"
    assert payload["temperature_celsius"] == 22.5


@pytest.mark.asyncio
async def test_mcp_missing_city_is_an_error_string():
    text = await get_current_weather("")
    assert text.startswith("Error:")
    assert "city" in text.lower()


@pytest.mark.asyncio
async def test_mcp_unknown_city():
    text = await get_weather_forecast("Atlantis", days=3)
    assert text.startswith("Error:")
    assert "Unknown city" in text


@pytest.mark.asyncio
async def test_mcp_list_cities_tool():
    text = await list_available_cities()
    payload = json.loads(text)
    assert payload["count"] == 10
    assert "Sydney" in payload["available_cities"]


@pytest.mark.asyncio
async def test_execute_weather_tool_unknown():
    client = WeatherClient()
    with pytest.raises(ValueError, match="Unknown tool"):
        await execute_weather_tool(client, "nope", {})


@pytest.mark.asyncio
async def test_compare_rejects_empty_list():
    text = await compare_cities_weather([])
    assert text.startswith("Error:")
