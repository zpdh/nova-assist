"""Value types for the brain layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class Message:
    """One conversation message in the OpenAI chat format."""

    role: Role
    content: str | None = None
    tool_calls: tuple[dict[str, Any], ...] = ()
    tool_call_id: str | None = None
    name: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the wire format, omitting empty fields."""
        payload: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            payload["content"] = self.content
        if self.tool_calls:
            payload["tool_calls"] = list(self.tool_calls)
        if self.tool_call_id is not None:
            payload["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            payload["name"] = self.name
        return payload


@dataclass(frozen=True)
class SearchResult:
    """One web search hit."""

    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class Completion:
    """One raw model response, as returned by the chat client.

    Internal to the brain layer: the tool loop reads ``tool_calls`` to decide
    whether to keep going.
    """

    text: str = ""
    model: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatResult:
    """The outcome of one assistant turn.

    ``turns`` holds the messages generated this turn (assistant tool-call turns,
    tool results, and the final assistant turn) so the caller can persist them.
    """

    text: str
    model: str = ""
    turns: tuple[Message, ...] = ()
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    """A tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]
