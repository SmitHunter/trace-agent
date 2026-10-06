"""Tool executor that discovers and invokes tools over MCP."""

from __future__ import annotations

import time
from typing import Any

from .mcp_session import McpSession, McpToolError
from .models import ToolCall, ToolResult

# The MCP server wraps both validation and upstream failures as Error: text.
# Open-Meteo messages are the only ones worth retrying.
_TRANSIENT_MARKERS = ("Open-Meteo",)


def _is_transient(message: str) -> bool:
    return any(marker in message for marker in _TRANSIENT_MARKERS)


class ToolExecutor:
    """Runs tools through an MCP client (list_tools / call_tool)."""

    def __init__(self, session: McpSession) -> None:
        self.session = session
        self._tools: list[dict[str, Any]] | None = None

    async def get_tools(self) -> list[dict[str, Any]]:
        """Discover tools via MCP tools/list."""
        if self._tools is None:
            self._tools = await self.session.list_tools()
        return self._tools

    async def execute(self, tool_call: ToolCall, max_retries: int = 2) -> ToolResult:
        """Execute a tool via MCP tools/call, retrying transient upstream failures."""
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            start_time = time.perf_counter()
            try:
                result = await self.session.call_tool(tool_call.name, tool_call.arguments)
                duration_ms = (time.perf_counter() - start_time) * 1000
                return ToolResult(
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    result=result,
                    success=True,
                    duration_ms=duration_ms,
                )
            except McpToolError as exc:
                last_error = exc
                duration_ms = (time.perf_counter() - start_time) * 1000
                if _is_transient(str(exc)) and attempt < max_retries:
                    continue
                prefix = f"Error after {attempt + 1} attempts: " if attempt > 0 else ""
                return ToolResult(
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    result=f"{prefix}{exc}",
                    success=False,
                    duration_ms=duration_ms,
                )

        return ToolResult(
            tool_call_id=tool_call.id,
            name=tool_call.name,
            result=f"Error: {last_error}",
            success=False,
            duration_ms=0,
        )

    async def close(self) -> None:
        """Session lifetime is owned by the Agent or the API lifespan."""
        return None
