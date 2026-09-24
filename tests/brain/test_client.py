"""Tests for :mod:`nova.brain.client`."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from nova.brain.client import ChatClient, decode_first_json, parse_tool_arguments
from nova.brain.errors import BrainError
from nova.brain.types import Message

_CHAT_RESPONSE = {
    "model": "test-model",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello"}}],
    "usage": {"total_tokens": 5},
}


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.server.last_body = json.loads(body) if body else {}
        payload = self.server.response_body
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_chat_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    server.status = 200
    server.response_body = json.dumps(_CHAT_RESPONSE).encode()
    server.last_body = {}
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def _client(server, **overrides):
    return ChatClient(f"http://127.0.0.1:{server.server_address[1]}", "key", "test-model")


def test_complete_returns_text(fake_chat_server):
    client = _client(fake_chat_server)

    result = client.complete([Message(role="user", content="hi")])

    assert result.text == "hello"
    assert result.model == "test-model"
    assert result.usage == {"total_tokens": 5}
    client.close()


def test_complete_sends_tools_when_given(fake_chat_server):
    client = _client(fake_chat_server)
    tools = [{"type": "function", "function": {"name": "web_search"}}]

    client.complete([Message(role="user", content="hi")], tools=tools)

    assert fake_chat_server.last_body["tools"] == tools
    client.close()


def test_padded_and_sse_terminated_body_is_parsed(fake_chat_server):
    padded = ("\n   \n" + json.dumps(_CHAT_RESPONSE) + "data: [DONE]").encode()
    fake_chat_server.response_body = padded
    client = _client(fake_chat_server)

    result = client.complete([Message(role="user", content="hi")])

    assert result.text == "hello"
    client.close()


def test_non_200_raises_brain_error(fake_chat_server):
    fake_chat_server.status = 403
    fake_chat_server.response_body = b'{"error":"nope"}'
    client = _client(fake_chat_server)

    with pytest.raises(BrainError, match="403"):
        client.complete([Message(role="user", content="hi")])
    client.close()


def test_no_choices_raises(fake_chat_server):
    fake_chat_server.response_body = json.dumps({"choices": []}).encode()
    client = _client(fake_chat_server)

    with pytest.raises(BrainError, match="no choices"):
        client.complete([Message(role="user", content="hi")])
    client.close()


def test_close_is_idempotent(fake_chat_server):
    client = _client(fake_chat_server)
    client.close()
    client.close()


def test_decode_first_json_ignores_noise():
    assert decode_first_json('  {"a": 1} extra') == {"a": 1}
    assert decode_first_json("no json here") is None


def test_parse_tool_arguments_variants():
    assert parse_tool_arguments('{"query": "x"}') == {"query": "x"}
    assert parse_tool_arguments({"query": "y"}) == {"query": "y"}
    assert parse_tool_arguments(None) == {}
    assert parse_tool_arguments("not json") == {}
