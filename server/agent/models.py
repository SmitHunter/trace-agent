"""Data models for the agent."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class TraceEventType(StrEnum):
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RETRY = "retry"
    ERROR = "error"
    GUARDRAIL = "guardrail"
    PLANNING = "planning"


@dataclass
class Message:
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
        }


@dataclass
class ToolResult:
    tool_call_id: str
    name: str
    result: str
    success: bool
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "result": self.result,
            "success": self.success,
            "duration_ms": self.duration_ms,
        }


@dataclass
class TraceEvent:
    type: TraceEventType
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class AgentResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "finish_reason": self.finish_reason,
        }


@dataclass
class ConversationState:
    messages: list[Message] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)

    def add_message(self, role: MessageRole, content: str) -> None:
        self.messages.append(Message(role=role, content=content))

    def add_trace(
        self, event_type: TraceEventType, content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        self.trace.append(
            TraceEvent(
                type=event_type,
                content=content,
                metadata=metadata or {},
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": [m.to_dict() for m in self.messages],
            "trace": [t.to_dict() for t in self.trace],
            "tool_results": [tr.to_dict() for tr in self.tool_results],
        }
