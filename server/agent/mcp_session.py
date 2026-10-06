"""MCP client used by the web agent to talk to the weather server."""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.server.mcpserver import MCPServer


class McpToolError(Exception):
    """A tools/call completed but the server reported a tool-level error."""


def default_stdio_parameters() -> StdioServerParameters:
    """Launch the same stdio server Claude Desktop and Cursor use."""
    server_dir = Path(__file__).resolve().parents[1]
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(server_dir),
    )


def default_mcp_target() -> MCPServer | StdioServerParameters:
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "inprocess":
        from mcp_server.server import mcp

        return mcp
    return default_stdio_parameters()


def _tool_text(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _to_llm_tool(tool: Any) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description or "",
        "inputSchema": tool.input_schema or {"type": "object", "properties": {}},
    }


class McpSession:
    """Long-lived MCP client. Discovers tools with list_tools and runs call_tool.

    The SDK client is owned by a dedicated asyncio task so ``__aenter__`` and
    ``__aexit__`` run in the same task. pytest-asyncio fixtures otherwise close
    the client from a different task than the one that opened it.
    """

    def __init__(self, target: MCPServer | StdioServerParameters | None = None) -> None:
        self._target = target if target is not None else default_mcp_target()
        self._client: Client | None = None
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._start_error: BaseException | None = None
        self.transport = "inprocess" if isinstance(self._target, MCPServer) else "stdio"

    async def connect(self) -> None:
        if self._client is not None:
            return
        if self._task is None or self._task.done():
            self._ready = asyncio.Event()
            self._stop = asyncio.Event()
            self._start_error = None
            self._task = asyncio.create_task(self._run(), name="mcp-session")
        await self._ready.wait()
        if self._start_error is not None:
            raise RuntimeError("MCP session failed to start") from self._start_error
        if self._client is None:
            raise RuntimeError("MCP session failed to start")

    async def _run(self) -> None:
        kwargs: dict[str, Any] = {}
        if isinstance(self._target, MCPServer):
            # Force the initialize handshake and JSON-RPC framing, not the
            # in-process shortcut that skips the protocol.
            kwargs["mode"] = "legacy"
        try:
            async with Client(self._target, **kwargs) as client:
                self._client = client
                self._ready.set()
                await self._stop.wait()
        except Exception as exc:
            self._start_error = exc
            self._ready.set()
            raise
        finally:
            self._client = None

    async def list_tools(self) -> list[dict[str, Any]]:
        await self.connect()
        assert self._client is not None
        async with self._lock:
            result = await self._client.list_tools()
        return [_to_llm_tool(tool) for tool in result.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        await self.connect()
        assert self._client is not None
        async with self._lock:
            result = await self._client.call_tool(name, arguments or {})
        text = _tool_text(result)
        if result.is_error or text.startswith("Error:"):
            raise McpToolError(text or "MCP tool returned an error")
        return text

    async def close(self) -> None:
        task = self._task
        self._task = None
        self._stop.set()
        if task is None:
            return
        with suppress(asyncio.CancelledError):
            await task
