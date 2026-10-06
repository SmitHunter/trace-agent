"""FastAPI application for the trace-agent."""

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.agent import Agent
from agent.guardrails import Guardrails
from agent.mcp_session import McpSession
from agent.models import ConversationState

sessions: dict[str, tuple[Agent, ConversationState]] = {}
MAX_SESSIONS = 100
mcp_session: McpSession | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global mcp_session
    session = McpSession()
    await session.connect()
    mcp_session = session
    yield
    for _session_id, (agent, _) in list(sessions.items()):
        await agent.close()
    sessions.clear()
    await session.close()
    mcp_session = None


app = FastAPI(
    title="Trace Agent API",
    description="AI Agent with MCP tools and visible reasoning traces",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3847,http://127.0.0.1:3847",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=Guardrails.MAX_INPUT_LENGTH,
        description="User message to send to the agent",
    )
    session_id: str | None = Field(None, description="Session ID for conversation continuity")


class TraceEventResponse(BaseModel):
    type: str
    content: str
    timestamp: str
    metadata: dict[str, Any]


class ToolResultResponse(BaseModel):
    tool_call_id: str
    name: str
    result: str
    success: bool
    duration_ms: float


class ChatResponse(BaseModel):
    response: str
    session_id: str
    trace: list[TraceEventResponse]
    tool_results: list[ToolResultResponse]
    demo_mode: bool


class SessionResponse(BaseModel):
    session_id: str
    message_count: int
    demo_mode: bool
    created_at: str


class HealthResponse(BaseModel):
    status: str
    demo_mode: bool
    timestamp: str


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check API health status."""
    demo_mode = os.getenv("DEMO_MODE", "").lower() == "true" or not (
        os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    )
    return HealthResponse(
        status="healthy",
        demo_mode=demo_mode,
        timestamp=datetime.now(UTC).isoformat(),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to the agent and get a response with traces."""
    session_id = request.session_id or str(uuid.uuid4())

    if session_id in sessions:
        agent, conversation = sessions[session_id]
    else:
        await _evict_oldest_session_if_needed()
        agent = Agent(mcp_session=_require_mcp_session())
        conversation = ConversationState()
        sessions[session_id] = (agent, conversation)

    trace_start_idx = len(conversation.trace)
    tool_start_idx = len(conversation.tool_results)

    try:
        response, updated_conversation = await agent.chat(request.message, conversation)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}") from e

    sessions[session_id] = (agent, updated_conversation)

    new_traces = updated_conversation.trace[trace_start_idx:]
    new_tool_results = updated_conversation.tool_results[tool_start_idx:]

    return ChatResponse(
        response=response,
        session_id=session_id,
        trace=[
            TraceEventResponse(
                type=t.type.value,
                content=t.content,
                timestamp=t.timestamp.isoformat(),
                metadata=t.metadata,
            )
            for t in new_traces
        ],
        tool_results=[
            ToolResultResponse(
                tool_call_id=tr.tool_call_id,
                name=tr.name,
                result=tr.result,
                success=tr.success,
                duration_ms=tr.duration_ms,
            )
            for tr in new_tool_results
        ],
        demo_mode=agent.demo_mode,
    )


@app.post("/sessions", response_model=SessionResponse)
async def create_session() -> SessionResponse:
    """Create a new conversation session."""
    await _evict_oldest_session_if_needed()
    session_id = str(uuid.uuid4())
    agent = Agent(mcp_session=_require_mcp_session())
    conversation = ConversationState()
    sessions[session_id] = (agent, conversation)

    return SessionResponse(
        session_id=session_id,
        message_count=0,
        demo_mode=agent.demo_mode,
        created_at=datetime.now(UTC).isoformat(),
    )


@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """Get session information."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    agent, conversation = sessions[session_id]
    user_messages = [m for m in conversation.messages if m.role.value == "user"]

    return SessionResponse(
        session_id=session_id,
        message_count=len(user_messages),
        demo_mode=agent.demo_mode,
        created_at=conversation.messages[0].timestamp.isoformat()
        if conversation.messages
        else datetime.now(UTC).isoformat(),
    )


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete a conversation session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    agent, _ = sessions.pop(session_id)
    await agent.close()

    return {"status": "deleted", "session_id": session_id}


@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str) -> dict[str, Any]:
    """Get full conversation history for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    agent, conversation = sessions[session_id]

    return {
        "session_id": session_id,
        "demo_mode": agent.demo_mode,
        "messages": [
            {
                "role": m.role.value,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in conversation.messages
        ],
        "trace": [
            {
                "type": t.type.value,
                "content": t.content,
                "timestamp": t.timestamp.isoformat(),
                "metadata": t.metadata,
            }
            for t in conversation.trace
        ],
        "tool_results": [
            {
                "tool_call_id": tr.tool_call_id,
                "name": tr.name,
                "result": tr.result,
                "success": tr.success,
                "duration_ms": tr.duration_ms,
            }
            for tr in conversation.tool_results
        ],
    }


def _require_mcp_session() -> McpSession:
    if mcp_session is None:
        raise HTTPException(status_code=503, detail="MCP session is not connected")
    return mcp_session


async def _evict_oldest_session_if_needed() -> None:
    if len(sessions) < MAX_SESSIONS:
        return
    oldest_id, (oldest_agent, _) = next(iter(sessions.items()))
    sessions.pop(oldest_id, None)
    await oldest_agent.close()


def main() -> None:
    """Run the API server."""
    port = int(os.getenv("API_PORT", "8742"))
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("DEBUG", "").lower() == "true",
    )


if __name__ == "__main__":
    main()
