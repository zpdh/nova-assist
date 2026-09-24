"""The brain: turn a user message into an answer, using tools when needed.

Flow: send the conversation to the model with the available tools; if the model
requests a tool, run it and feed the result back; repeat up to a bounded number
of rounds. This is the Agent-style tool loop, implemented with a plain
request/response cycle rather than a framework.
"""

from __future__ import annotations

import logging
from typing import Any

from nova.brain.client import ChatClient, parse_tool_arguments
from nova.brain.router import ModelRouter
from nova.brain.tools import tool_schemas
from nova.brain.types import ChatResult, Message

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 2

SYSTEM_PROMPT = (
    "You are Nova, a concise voice assistant. Answer briefly and directly. "
    "Use the web_search tool when the answer needs current or verifiable facts."
)


class Brain:
    """Answers user messages, running tools the model asks for."""

    def __init__(
        self,
        client: ChatClient,
        router: ModelRouter,
        dispatchers: dict[str, Any],
    ) -> None:
        self._client = client
        self._router = router
        self._dispatchers = dispatchers

    def ask(self, text: str) -> str:
        """Answer a single user message and return the assistant's text."""
        return self.chat([Message(role="user", content=text)]).text

    def chat(self, messages: list[Message]) -> ChatResult:
        """Run the conversation, resolving tool calls, and return the result."""
        conversation = [Message(role="system", content=SYSTEM_PROMPT), *messages]
        result = self._client.complete(conversation, tools=tool_schemas())

        for round_index in range(MAX_TOOL_ROUNDS + 1):
            if not result.tool_calls:
                return result
            if round_index == MAX_TOOL_ROUNDS:
                log.warning("tool-call limit reached; returning current answer")
                return result

            conversation.append(
                Message(role="assistant", content=None, tool_calls=result.tool_calls)
            )
            conversation.extend(self._resolve_tool_calls(result.tool_calls))
            result = self._client.complete(conversation, tools=tool_schemas())

        return result

    def _resolve_tool_calls(self, tool_calls: tuple[dict[str, Any], ...]) -> list[Message]:
        messages = []
        for call in tool_calls:
            call_id = str(call.get("id", ""))
            function = call.get("function") or {}
            name = str(function.get("name", ""))
            arguments = parse_tool_arguments(function.get("arguments"))
            output = self._run_tool(name, arguments)
            messages.append(Message(role="tool", content=output, tool_call_id=call_id))
        return messages

    def _run_tool(self, name: str, arguments: dict[str, Any]) -> str:
        dispatcher = self._dispatchers.get(name)
        if dispatcher is None:
            log.warning("model requested unknown tool %r", name)
            return f"error: unknown tool {name!r}"
        try:
            return dispatcher(arguments)
        except Exception as exc:  # noqa: BLE001 (feed any tool error back to the model)
            log.warning("tool %r failed: %s", name, exc)
            return f"error: tool {name!r} failed: {exc}"

    def close(self) -> None:
        """Release the chat client's transport."""
        self._client.close()


__all__ = ["Brain", "MAX_TOOL_ROUNDS", "SYSTEM_PROMPT"]
