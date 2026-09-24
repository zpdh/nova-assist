"""Tests for :mod:`nova.brain.tools`."""

from __future__ import annotations

from nova.brain.tools import build_dispatchers, tool_schemas
from nova.brain.types import SearchResult


class _FakeSearch:
    def __init__(self, results=None):
        self._results = results or []
        self.seen = None

    def search(self, query, max_results=5):
        self.seen = query
        return self._results


def test_tool_schemas_shape():
    schemas = tool_schemas()

    assert len(schemas) == 1
    function = schemas[0]["function"]
    assert function["name"] == "web_search"
    assert function["parameters"]["required"] == ["query"]


def test_web_search_dispatcher_formats_results():
    search = _FakeSearch([SearchResult(title="T", url="http://a", snippet="S")])
    dispatchers = build_dispatchers(search)

    output = dispatchers["web_search"]({"query": "hello"})

    assert search.seen == "hello"
    assert "T" in output and "http://a" in output and "S" in output


def test_web_search_missing_query():
    dispatchers = build_dispatchers(_FakeSearch())

    assert "missing" in dispatchers["web_search"]({})


def test_web_search_no_results():
    dispatchers = build_dispatchers(_FakeSearch([]))

    assert dispatchers["web_search"]({"query": "x"}) == "no results found"
