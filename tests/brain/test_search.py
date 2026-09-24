"""Tests for :mod:`nova.brain.search`."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from nova.brain.errors import BrainError
from nova.brain.search import WebSearchClient

_SEARCH_RESPONSE = {
    "provider": "tavily",
    "query": "x",
    "results": [
        {"title": "T1", "url": "http://a", "snippet": "s1"},
        {"title": "T2", "url": "http://b", "content": "c2"},
    ],
}


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.server.last_body = json.loads(self.rfile.read(length))
        payload = self.server.response_body
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_search_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    server.status = 200
    server.response_body = json.dumps(_SEARCH_RESPONSE).encode()
    server.last_body = {}
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def _client(server):
    return WebSearchClient(f"http://127.0.0.1:{server.server_address[1]}", "key", "tavily")


def test_search_returns_results(fake_search_server):
    client = _client(fake_search_server)

    results = client.search("x", max_results=2)

    assert [r.title for r in results] == ["T1", "T2"]
    assert results[0].url == "http://a"
    assert results[1].snippet == "c2"  # falls back to content
    client.close()


def test_search_sends_provider_and_query(fake_search_server):
    client = _client(fake_search_server)

    client.search("hello world", max_results=3)

    assert fake_search_server.last_body["model"] == "tavily"
    assert fake_search_server.last_body["query"] == "hello world"
    assert fake_search_server.last_body["max_results"] == 3
    client.close()


def test_non_200_raises(fake_search_server):
    fake_search_server.status = 500
    fake_search_server.response_body = b"boom"
    client = _client(fake_search_server)

    with pytest.raises(BrainError, match="500"):
        client.search("x")
    client.close()


def test_empty_results(fake_search_server):
    fake_search_server.response_body = json.dumps({"results": []}).encode()
    client = _client(fake_search_server)

    assert client.search("x") == []
    client.close()
