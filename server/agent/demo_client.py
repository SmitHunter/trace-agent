"""Demo mode LLM client with pre-recorded responses for testing without API keys."""

import json
import re
from typing import Any

from .llm_client import LLMClient
from .models import AgentResponse, ToolCall

DEMO_SCENARIOS: dict[str, list[dict[str, Any]]] = {
    "compare": [
        {
            "pattern": r"(compare|warmer|cooler|difference|hottest|coldest)",
            "responses": [
                {
                    "tool_calls": [
                        {
                            "id": "demo_3",
                            "name": "compare_cities_weather",
                            "arguments": {"cities": ["Sydney", "Melbourne", "Brisbane"]},
                        }
                    ],
                    "content": "",
                },
                {
                    "tool_calls": [],
                    "content": "PARSE_TOOL_RESULT:compare",
                },
            ],
        }
    ],
    "forecast": [
        {
            "pattern": r"(forecast|next|week|tomorrow|days).*(sydney|melbourne|brisbane|perth|adelaide|canberra|hobart|darwin|gold coast|newcastle)",
            "responses": [
                {
                    "tool_calls": [
                        {
                            "id": "demo_2",
                            "name": "get_weather_forecast",
                            "arguments": {"city": "{city}", "days": 7},
                        }
                    ],
                    "content": "",
                },
                {
                    "tool_calls": [],
                    "content": "PARSE_TOOL_RESULT:forecast",
                },
            ],
        }
    ],
    "list_cities": [
        {
            "pattern": r"(list|available|supported|which).*(cities|city|locations)",
            "responses": [
                {
                    "tool_calls": [
                        {
                            "id": "demo_4",
                            "name": "list_available_cities",
                            "arguments": {},
                        }
                    ],
                    "content": "",
                },
                {
                    "tool_calls": [],
                    "content": (
                        "I can provide weather information for these Australian cities:\n\n"
                        "🏙️ **Major Cities**: Sydney, Melbourne, Brisbane, Perth, Adelaide\n"
                        "🏛️ **Capital**: Canberra\n"
                        "🌴 **Regional**: Darwin, Hobart, Gold Coast, Newcastle\n\n"
                        "Just ask about the weather in any of these cities!"
                    ),
                },
            ],
        }
    ],
    "planning_question": [
        {
            "pattern": r"(should i|planning|trip|visit|travel|best time|good day)",
            "responses": [
                {
                    "tool_calls": [
                        {
                            "id": "demo_5",
                            "name": "get_weather_forecast",
                            "arguments": {"city": "Sydney", "days": 7},
                        }
                    ],
                    "content": "Let me check the forecast to help with your planning.",
                },
                {
                    "tool_calls": [
                        {
                            "id": "demo_6",
                            "name": "compare_cities_weather",
                            "arguments": {"cities": ["Sydney", "Melbourne", "Brisbane"]},
                        }
                    ],
                    "content": "Now let me compare with other cities to give you options.",
                },
                {
                    "tool_calls": [],
                    "content": "PARSE_TOOL_RESULT:planning",
                },
            ],
        }
    ],
    "weather_current": [
        {
            "pattern": r"(weather|temperature|hot|cold|rain).*(sydney|melbourne|brisbane|perth|adelaide|canberra|hobart|darwin|gold coast|newcastle)",
            "responses": [
                {
                    "tool_calls": [
                        {
                            "id": "demo_1",
                            "name": "get_current_weather",
                            "arguments": {"city": "{city}"},
                        }
                    ],
                    "content": "",
                },
                {
                    "tool_calls": [],
                    "content": "PARSE_TOOL_RESULT:current_weather",
                },
            ],
        }
    ],
}

DEFAULT_RESPONSE: dict[str, Any] = {
    "tool_calls": [],
    "content": (
        "I'm a weather assistant for Australian cities. I can help you with:\n\n"
        "• **Current weather** - Ask about conditions in any major Australian city\n"
        "• **Forecasts** - Get up to 16-day forecasts\n"
        "• **Comparisons** - Compare weather across cities\n"
        "• **Trip planning** - Get recommendations based on weather\n\n"
        "Try asking something like:\n"
        '- "What\'s the weather in Sydney?"\n'
        '- "Give me a 7-day forecast for Melbourne"\n'
        '- "Which city is warmer, Sydney or Brisbane?"'
    ),
}


class DemoLLMClient(LLMClient):
    """Demo LLM client with pre-recorded responses."""

    def __init__(self) -> None:
        self._response_index: dict[str, int] = {}
        self._current_scenario: str | None = None

    def _find_scenario(self, user_message: str) -> tuple[str, dict[str, Any]] | None:
        """Find a matching scenario for the user message."""
        message_lower = user_message.lower()

        for scenario_name, patterns in DEMO_SCENARIOS.items():
            for pattern_data in patterns:
                if re.search(pattern_data["pattern"], message_lower, re.IGNORECASE):
                    return scenario_name, pattern_data

        return None

    def _extract_city(self, message: str) -> str:
        """Extract city name from message."""
        cities = [
            "sydney",
            "melbourne",
            "brisbane",
            "perth",
            "adelaide",
            "canberra",
            "hobart",
            "darwin",
            "gold coast",
            "newcastle",
        ]
        message_lower = message.lower()
        for city in cities:
            if city in message_lower:
                return city.title()
        return "Sydney"

    def _format_current_weather(self, data: dict[str, Any]) -> str:
        """Format current weather data into a readable response."""
        return (
            f"Based on the current weather data for **{data.get('city', 'the city')}**:\n\n"
            f"🌡️ **Temperature**: {data.get('temperature_celsius', 'N/A')}°C "
            f"(feels like {data.get('feels_like_celsius', 'N/A')}°C)\n"
            f"☁️ **Conditions**: {data.get('conditions', 'Unknown')}\n"
            f"💨 **Wind**: {data.get('wind_speed_kmh', 'N/A')} km/h\n"
            f"💧 **Humidity**: {data.get('humidity_percent', 'N/A')}%\n\n"
            f"{'☀️ It is currently daytime.' if data.get('is_daytime') else '🌙 It is currently nighttime.'}"
        )

    def _format_forecast(self, data: dict[str, Any]) -> str:
        """Format forecast data into a readable response."""
        city = data.get("city", "the city")
        forecast = data.get("forecast", [])

        lines = [f"Here's the weather forecast for **{city}**:\n"]
        for day in forecast[:7]:
            lines.append(
                f"📅 **{day.get('date', '')}**: "
                f"{day.get('conditions', '')} | "
                f"High: {day.get('high_celsius', 'N/A')}°C, "
                f"Low: {day.get('low_celsius', 'N/A')}°C | "
                f"Rain: {day.get('precipitation_chance_percent', 0)}%"
            )

        return "\n".join(lines)

    def _format_comparison(self, data: dict[str, Any]) -> str:
        """Format comparison data into a readable response."""
        lines = ["Here's a comparison of weather across the cities:\n"]

        summary = data.pop("_summary", {})

        for city, info in data.items():
            if isinstance(info, dict) and "temperature_celsius" in info:
                lines.append(
                    f"• **{city}**: {info.get('temperature_celsius', 'N/A')}°C, "
                    f"{info.get('conditions', 'Unknown')}, "
                    f"humidity {info.get('humidity_percent', 'N/A')}%"
                )

        if summary:
            hottest = summary.get("hottest", {})
            coldest = summary.get("coldest", {})
            lines.append("")
            lines.append(
                f"🏆 **Warmest**: {hottest.get('city', 'N/A')} at {hottest.get('temperature', 'N/A')}°C"
            )
            lines.append(
                f"❄️ **Coolest**: {coldest.get('city', 'N/A')} at {coldest.get('temperature', 'N/A')}°C"
            )

        return "\n".join(lines)

    def _format_planning(self, tool_results: list[str]) -> str:
        """Format planning response from tool results."""
        lines = ["Based on my analysis of the weather data:\n"]

        for result in tool_results:
            try:
                data = json.loads(result)
                if "forecast" in data:
                    best_days = []
                    for day in data.get("forecast", [])[:3]:
                        if day.get("precipitation_chance_percent", 100) < 30:
                            best_days.append(day.get("date", ""))
                    if best_days:
                        lines.append(
                            f"📊 **Best Days for Outdoor Activities**: {', '.join(best_days)}"
                        )
            except (json.JSONDecodeError, KeyError):
                pass

        lines.append("\n💡 **Recommendation**: The upcoming days look good for outdoor activities!")
        return "\n".join(lines)

    def _parse_tool_result_content(self, content: str, tool_messages: list[dict[str, Any]]) -> str:
        """Parse tool results and generate formatted response."""
        if not content.startswith("PARSE_TOOL_RESULT:"):
            return content

        result_type = content.split(":")[1]

        tool_results = [m.get("content", "") for m in tool_messages]

        if result_type == "current_weather" and tool_results:
            try:
                data = json.loads(tool_results[-1])
                return self._format_current_weather(data)
            except json.JSONDecodeError:
                return "I retrieved the weather data but encountered an error formatting it."

        elif result_type == "forecast" and tool_results:
            try:
                data = json.loads(tool_results[-1])
                return self._format_forecast(data)
            except json.JSONDecodeError:
                return "I retrieved the forecast but encountered an error formatting it."

        elif result_type == "compare" and tool_results:
            try:
                data = json.loads(tool_results[-1])
                return self._format_comparison(data)
            except json.JSONDecodeError:
                return "I retrieved the comparison but encountered an error formatting it."

        elif result_type == "planning":
            return self._format_planning(tool_results)

        return content

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AgentResponse:
        user_messages = [m for m in messages if m.get("role") == "user"]
        if not user_messages:
            return AgentResponse(content=DEFAULT_RESPONSE["content"], tool_calls=[])

        last_user_message = str(user_messages[-1].get("content", ""))

        tool_messages = [m for m in messages if m.get("role") == "tool"]

        if tool_messages and self._current_scenario:
            scenario_data = None
            for patterns in DEMO_SCENARIOS.values():
                for pattern_data in patterns:
                    if re.search(pattern_data["pattern"], last_user_message.lower(), re.IGNORECASE):
                        scenario_data = pattern_data
                        break
                if scenario_data:
                    break

            if not scenario_data:
                fallback = DEMO_SCENARIOS.get(self._current_scenario, [])
                if fallback:
                    scenario_data = fallback[0]

            if scenario_data:
                idx = self._response_index.get(self._current_scenario, 0)
                responses = scenario_data["responses"]
                if idx < len(responses):
                    response_data = responses[idx]
                    self._response_index[self._current_scenario] = idx + 1

                    tool_calls = [
                        ToolCall(
                            id=tc["id"],
                            name=tc["name"],
                            arguments=tc["arguments"],
                        )
                        for tc in response_data.get("tool_calls", [])
                    ]

                    content = response_data["content"]
                    if content.startswith("PARSE_TOOL_RESULT:"):
                        content = self._parse_tool_result_content(content, tool_messages)

                    return AgentResponse(
                        content=content,
                        tool_calls=tool_calls,
                        finish_reason="tool_calls" if tool_calls else "stop",
                    )

        match = self._find_scenario(last_user_message)

        if match:
            scenario_name, pattern_data = match
            self._current_scenario = scenario_name
            self._response_index[scenario_name] = 1

            response_data = pattern_data["responses"][0]
            city = self._extract_city(last_user_message)

            tool_calls = []
            for tc in response_data.get("tool_calls", []):
                args = tc["arguments"].copy()
                if "city" in args and args["city"] == "{city}":
                    args["city"] = city
                tool_calls.append(
                    ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=args,
                    )
                )

            return AgentResponse(
                content=response_data["content"],
                tool_calls=tool_calls,
                finish_reason="tool_calls" if tool_calls else "stop",
            )

        self._current_scenario = None
        return AgentResponse(content=DEFAULT_RESPONSE["content"], tool_calls=[])
