"""Tool definitions exposed to the model, and their dispatch.

A tool is a function the model may ask the brain to run. The schema below
follows the OpenAI function-calling format. Dispatch maps a tool name to a
callable that takes the decoded arguments and returns a string to feed back.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nova.brain.search import WebSearchClient
from nova.brain.types import SearchResult

TOOL_NAMES = ("web_search",)

_WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use it for recent events, "
            "facts you are unsure about, or anything needing up-to-date sources."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                }
            },
            "required": ["query"],
        },
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    """Return the schemas for all tools the brain exposes."""
    return [_WEB_SEARCH_SCHEMA]


def build_dispatchers(search: WebSearchClient) -> dict[str, Callable[[dict[str, Any]], str]]:
    """Map tool names to callables bound to the given clients."""
    return {"web_search": _make_web_search(search)}


def _make_web_search(search: WebSearchClient) -> Callable[[dict[str, Any]], str]:
	# Return a callable that already holds the search client, so the dispatch
    # table maps a tool name to a one-argument function (the tool arguments).
    # This keeps the brain unaware of which clients each tool needs.
    def run(arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip()
        if not query:
            return "error: missing 'query' argument"

        results = search.search(query)
        return _format_results(results)

    return run


def _format_results(results: list[SearchResult]) -> str:
    if not results:
        return "no results found"

    lines = []
    for i, result in enumerate(results, start=1):
        lines.append(f"{i}. {result.title}\n   {result.url}\n   {result.snippet}")
    return "\n".join(lines)
