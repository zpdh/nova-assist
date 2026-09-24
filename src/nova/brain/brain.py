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
from nova.brain.types import ChatResult, Completion, Message

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 2


class Brain:
    """Answers user messages, running tools the model asks for.

    The brain is stateless: it sends the messages it is given and returns the
    assistant's turn. The system prompt and conversation history are supplied by
    the caller (for example, the session service).
    """

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
        """Run the conversation, resolving tool calls, and return the result.

        ``turns`` on the result holds the messages generated this turn
        (assistant tool-call turns, tool results, and the final assistant turn)
        so the caller can persist them.
        """
        conversation = list(messages)
        result = self._client.complete(conversation, tools=tool_schemas())
        generated: list[Message] = []

        for round_index in range(MAX_TOOL_ROUNDS + 1):
            if not result.tool_calls:
                if result.text:
                    generated.append(Message(role="assistant", content=result.text))
                return _with_turns(result, generated)
            if round_index == MAX_TOOL_ROUNDS:
                log.warning("tool-call limit reached; returning current answer")
                generated.append(
                    Message(role="assistant", content=None, tool_calls=result.tool_calls)
                )
                return _with_turns(result, generated)

            assistant_turn = Message(role="assistant", content=None, tool_calls=result.tool_calls)
            conversation.append(assistant_turn)
            generated.append(assistant_turn)

            tool_turns = self._resolve_tool_calls(result.tool_calls)
            conversation.extend(tool_turns)
            generated.extend(tool_turns)

            result = self._client.complete(conversation, tools=tool_schemas())

        return _with_turns(result, generated)

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


def _with_turns(result: Completion, generated: list[Message]) -> ChatResult:
    """Return a :class:`ChatResult` built from ``result`` and the generated turns."""
    return ChatResult(
        text=result.text,
        model=result.model,
        turns=tuple(generated),
        usage=result.usage,
    )


__all__ = ["Brain", "MAX_TOOL_ROUNDS"]
