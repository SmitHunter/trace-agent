"""Limits that keep the agent loop bounded. Not a security boundary."""

from dataclasses import dataclass
from typing import Any


@dataclass
class GuardrailResult:
    passed: bool
    message: str
    details: dict[str, Any] | None = None


class Guardrails:
    """Hard limits for input size, tool fan-out, and conversation length."""

    MAX_TOOL_CALLS_PER_TURN = 5
    MAX_CONVERSATION_TURNS = 20
    MAX_INPUT_LENGTH = 2000
    MAX_RESPONSE_LENGTH = 10000

    def check_input(self, user_input: str) -> GuardrailResult:
        """Reject oversized user input before it reaches the model."""
        if len(user_input) > self.MAX_INPUT_LENGTH:
            return GuardrailResult(
                passed=False,
                message=f"Input too long. Maximum {self.MAX_INPUT_LENGTH} characters allowed.",
                details={"length": len(user_input)},
            )
        return GuardrailResult(passed=True, message="Input OK")

    def check_tool_calls(
        self, tool_calls: list[dict[str, Any]], turn_count: int
    ) -> GuardrailResult:
        """Cap how many tools the model can fire in one iteration."""
        if len(tool_calls) > self.MAX_TOOL_CALLS_PER_TURN:
            return GuardrailResult(
                passed=False,
                message=f"Too many tool calls. Maximum {self.MAX_TOOL_CALLS_PER_TURN} per turn.",
                details={"tool_call_count": len(tool_calls), "turn_count": turn_count},
            )
        return GuardrailResult(passed=True, message="Tool calls OK")

    def check_conversation_length(self, turn_count: int) -> GuardrailResult:
        """Stop unbounded in-memory conversations."""
        if turn_count >= self.MAX_CONVERSATION_TURNS:
            return GuardrailResult(
                passed=False,
                message=(
                    f"Conversation too long. Maximum {self.MAX_CONVERSATION_TURNS} turns. "
                    "Please start a new conversation."
                ),
                details={"turn_count": turn_count},
            )
        return GuardrailResult(passed=True, message="Conversation length OK")

    def check_tool_arguments(self, tool_name: str, arguments: dict[str, Any]) -> GuardrailResult:
        """Validate arguments before a tool runs."""
        if tool_name == "get_current_weather":
            city = arguments.get("city", "")
            if not city or not isinstance(city, str):
                return GuardrailResult(passed=False, message="Invalid city parameter")
            if len(city) > 100:
                return GuardrailResult(passed=False, message="City name too long")

        elif tool_name == "get_weather_forecast":
            city = arguments.get("city", "")
            if not city or not isinstance(city, str):
                return GuardrailResult(passed=False, message="Invalid city parameter")
            days = arguments.get("days", 7)
            if isinstance(days, float) and days.is_integer():
                days = int(days)
            if not isinstance(days, int) or days < 1 or days > 16:
                return GuardrailResult(passed=False, message="Days must be between 1 and 16")

        elif tool_name == "compare_cities_weather":
            cities = arguments.get("cities", [])
            if not isinstance(cities, list) or not cities or len(cities) > 5:
                return GuardrailResult(
                    passed=False,
                    message="Cities must be a list of 1 to 5 items",
                )

        return GuardrailResult(passed=True, message="Arguments OK")

    def check_response(self, response: str) -> GuardrailResult:
        """Reject unexpectedly huge model output."""
        if len(response) > self.MAX_RESPONSE_LENGTH:
            return GuardrailResult(
                passed=False,
                message="Response too long",
                details={"length": len(response)},
            )
        return GuardrailResult(passed=True, message="Response OK")
