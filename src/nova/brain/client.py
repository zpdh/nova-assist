"""OpenAI-compatible chat client.

One reused ``httpx.Client`` posts to ``/chat/completions`` and returns a parsed
:class:`ChatResult`. The client owns its transport; callers supply messages and
optional tool schemas.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from nova.brain.errors import BrainError, BrainTimeout
from nova.brain.types import ChatResult, Message

log = logging.getLogger(__name__)

_REQUEST_TIMEOUT_S = 120.0


class ChatClient:
    """Client for an OpenAI-compatible ``/chat/completions`` endpoint."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.Client(
            timeout=_REQUEST_TIMEOUT_S,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    @property
    def model(self) -> str:
        return self._model

    def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        """Send ``messages`` and return the assistant's turn."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [m.to_payload() for m in messages],
        }
        if tools:
            payload["tools"] = tools

        url = f"{self._base_url}/chat/completions"
        try:
            response = self._client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise BrainTimeout(f"chat request timed out: {url}") from exc
        except httpx.HTTPError as exc:
            raise BrainError(f"chat request failed: {exc}") from exc

        if response.status_code != 200:
            raise BrainError(
                f"chat endpoint returned {response.status_code}: {response.text.strip()}"
            )

        document = _parse_json(response, "chat endpoint")
        return _parse_chat_result(document)

    def close(self) -> None:
        """Close the underlying HTTP client (idempotent)."""
        if not self._client.is_closed:
            self._client.close()


def _parse_json(response: httpx.Response, source: str) -> dict[str, Any]:
    # Some providers pad the body with whitespace and append an SSE-style
    # terminator (``data: [DONE]``). Decode the first JSON object in the body.
    document = decode_first_json(response.text)
    if document is None:
        raise BrainError(f"{source} returned invalid JSON")
    return document


def decode_first_json(text: str) -> dict[str, Any] | None:
    """Decode the first JSON object in ``text``, ignoring surrounding noise."""
    decoder = json.JSONDecoder()
    start = text.find("{")
    if start == -1:
        return None
    try:
        document, _ = decoder.raw_decode(text[start:])
    except ValueError:
        return None
    return document if isinstance(document, dict) else None


def _parse_chat_result(document: dict[str, Any]) -> ChatResult:
    choices = document.get("choices") or []
    if not choices:
        raise BrainError("chat endpoint returned no choices")

    message = choices[0].get("message") or {}
    tool_calls = tuple(message.get("tool_calls") or [])
    content = message.get("content")

    return ChatResult(
        text=content or "",
        model=str(document.get("model", "")),
        tool_calls=tool_calls,
        usage=document.get("usage") or {},
    )


def parse_tool_arguments(raw: Any) -> dict[str, Any]:
    """Decode a tool call's ``arguments`` field, which may be a JSON string."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except TypeError, ValueError:
        log.warning("could not parse tool arguments: %r", raw)
        return {}
    return decoded if isinstance(decoded, dict) else {}
