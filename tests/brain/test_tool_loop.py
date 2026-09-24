"""Tests for :class:`nova.brain.brain.Brain` and its tool loop."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from nova.brain.brain import MAX_TOOL_ROUNDS, Brain
from nova.brain.client import ChatClient
from nova.brain.router import SingleModelRouter
from nova.brain.types import Message

_TOOL_CALL = {
    "id": "call-1",
    "type": "function",
    "function": {"name": "web_search", "arguments": '{"query": "paris weather"}'},
}


class _ScriptedHandler(BaseHTTPRequestHandler):
    """Returns queued responses in order; records each request body."""

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.server.requests.append(json.loads(self.rfile.read(length)))
        payload = self.server.responses.pop(0)
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def scripted_server():
    server = HTTPServer(("127.0.0.1", 0), _ScriptedHandler)
    server.responses = []
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def _assistant(text=None, tool_calls=None):
    message = {"role": "assistant", "content": text}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {"model": "test-model", "choices": [{"index": 0, "message": message}]}


def _brain(server, dispatchers):
    client = ChatClient(f"http://127.0.0.1:{server.server_address[1]}", "key", "test-model")
    return Brain(client, SingleModelRouter("test-model"), dispatchers)


def test_plain_answer_without_tools(scripted_server):
    scripted_server.responses = [_assistant("plain answer")]
    brain = _brain(scripted_server, {})

    result = brain.chat([Message(role="user", content="hi")])

    assert result.text == "plain answer"
    assert [t.role for t in result.turns] == ["assistant"]
    assert result.turns[0].content == "plain answer"
    brain.close()


def test_tool_call_is_resolved_then_answered(scripted_server):
    scripted_server.responses = [
        _assistant(tool_calls=[_TOOL_CALL]),
        _assistant("grounded answer"),
    ]
    seen = {}

    def web_search(args):
        seen.update(args)
        return "RESULT LINES"

    brain = _brain(scripted_server, {"web_search": web_search})

    result = brain.chat([Message(role="user", content="weather?")])

    assert result.text == "grounded answer"
    assert seen == {"query": "paris weather"}
    # turns records the full transcript generated this turn.
    assert [t.role for t in result.turns] == ["assistant", "tool", "assistant"]
    assert result.turns[0].tool_calls[0]["id"] == "call-1"
    assert result.turns[1].content == "RESULT LINES"
    assert result.turns[1].tool_call_id == "call-1"
    assert result.turns[2].content == "grounded answer"
    # Second request carries the tool result back to the model.
    tool_messages = [m for m in scripted_server.requests[1]["messages"] if m["role"] == "tool"]
    assert tool_messages[0]["content"] == "RESULT LINES"
    assert tool_messages[0]["tool_call_id"] == "call-1"
    brain.close()


def test_unknown_tool_reports_error_without_crashing(scripted_server):
    scripted_server.responses = [
        _assistant(tool_calls=[_TOOL_CALL]),
        _assistant("recovered"),
    ]
    brain = _brain(scripted_server, {})

    assert brain.ask("x") == "recovered"
    tool_message = [m for m in scripted_server.requests[1]["messages"] if m["role"] == "tool"][0]
    assert "unknown tool" in tool_message["content"]
    brain.close()


def test_tool_failure_is_fed_back(scripted_server):
    scripted_server.responses = [
        _assistant(tool_calls=[_TOOL_CALL]),
        _assistant("handled failure"),
    ]

    def boom(args):
        raise RuntimeError("search down")

    brain = _brain(scripted_server, {"web_search": boom})

    assert brain.ask("x") == "handled failure"
    tool_message = [m for m in scripted_server.requests[1]["messages"] if m["role"] == "tool"][0]
    assert "search down" in tool_message["content"]
    brain.close()


def test_tool_loop_is_bounded(scripted_server):
    # Always request a tool; the loop must stop after MAX_TOOL_ROUNDS.
    scripted_server.responses = [_assistant(tool_calls=[_TOOL_CALL])] * (MAX_TOOL_ROUNDS + 2)
    brain = _brain(scripted_server, {"web_search": lambda args: "r"})

    result = brain.chat([Message(role="user", content="x")])

    assert result.text == ""  # no text was ever produced
    # 1 initial call + MAX_TOOL_ROUNDS follow-ups.
    assert len(scripted_server.requests) == MAX_TOOL_ROUNDS + 1
    # The last (unrun) assistant tool-call turn is still recorded.
    assert result.turns[-1].tool_calls[0]["id"] == "call-1"
    brain.close()
