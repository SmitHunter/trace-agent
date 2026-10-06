"""Shared weather tool definitions and execution used by MCP and the agent."""

from __future__ import annotations

from typing import Any

from .weather_client import WeatherClient

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_current_weather",
        "description": (
            "Get the current weather conditions for an Australian city. "
            "Returns temperature, humidity, wind, and conditions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": (
                        "Australian city name (e.g., Sydney, Melbourne, Brisbane, "
                        "Perth, Adelaide, Canberra, Hobart, Darwin, Gold Coast, Newcastle)"
                    ),
                }
            },
            "required": ["city"],
        },
    },
    {
        "name": "get_weather_forecast",
        "description": (
            "Get the weather forecast for an Australian city for up to 16 days. "
            "Returns daily high/low temperatures, conditions, and precipitation chances."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Australian city name",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to forecast (1-16)",
                    "minimum": 1,
                    "maximum": 16,
                    "default": 7,
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "compare_cities_weather",
        "description": (
            "Compare the current weather across multiple Australian cities. "
            "Useful for finding the warmest, coolest, or driest city."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Australian city names to compare (max 5)",
                    "maxItems": 5,
                }
            },
            "required": ["cities"],
        },
    },
    {
        "name": "list_available_cities",
        "description": "List all Australian cities supported by this weather service.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _as_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("days must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError("days must be an integer")


async def execute_weather_tool(
    client: WeatherClient,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Run one weather tool and return a JSON-serializable payload."""
    if name == "get_current_weather":
        city = arguments.get("city", "")
        if not city or not isinstance(city, str):
            raise ValueError("city parameter is required")
        weather = await client.get_current_weather(city)
        return weather.to_dict()

    if name == "get_weather_forecast":
        city = arguments.get("city", "")
        if not city or not isinstance(city, str):
            raise ValueError("city parameter is required")
        days = _as_int(arguments.get("days", 7), 7)
        forecast = await client.get_forecast(city, days)
        return {
            "city": city.title(),
            "forecast_days": len(forecast),
            "forecast": [day.to_dict() for day in forecast],
        }

    if name == "compare_cities_weather":
        cities = arguments.get("cities", [])
        if not cities or not isinstance(cities, list):
            raise ValueError("cities parameter is required")
        return await client.compare_weather([str(city) for city in cities])

    if name == "list_available_cities":
        cities = client.list_available_cities()
        return {
            "available_cities": cities,
            "count": len(cities),
        }

    raise ValueError(f"Unknown tool: {name}")
