"""Web search client over the gateway's ``/search`` endpoint.

The gateway proxies a search provider (default Tavily) and returns a list of
hits. The client reuses one ``httpx.Client`` and parses the result list into
:class:`SearchResult` values.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from nova.brain.client import parse_json_response
from nova.brain.errors import BrainError, BrainTimeout
from nova.brain.types import SearchResult

log = logging.getLogger(__name__)

_REQUEST_TIMEOUT_S = 60.0
_DEFAULT_MAX_RESULTS = 5


class WebSearchClient:
    """Client for the gateway's provider-backed search endpoint."""

    def __init__(self, base_url: str, api_key: str, provider: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._provider = provider
        self._client = httpx.Client(
            timeout=_REQUEST_TIMEOUT_S,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def search(self, query: str, max_results: int = _DEFAULT_MAX_RESULTS) -> list[SearchResult]:
        """Return up to ``max_results`` hits for ``query``."""
        payload = {
            "model": self._provider,
            "query": query,
            "max_results": max_results,
        }
        url = f"{self._base_url}/search"
        try:
            response = self._client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise BrainTimeout(f"search request timed out: {url}") from exc
        except httpx.HTTPError as exc:
            raise BrainError(f"search request failed: {exc}") from exc

        if response.status_code != 200:
            raise BrainError(
                f"search endpoint returned {response.status_code}: {response.text.strip()}"
            )

        document = parse_json_response(response, "search endpoint")

        return _parse_results(document)

    def close(self) -> None:
        """Close the underlying HTTP client (idempotent)."""
        if not self._client.is_closed:
            self._client.close()


def _parse_results(document: dict[str, Any]) -> list[SearchResult]:
    results = []
    for item in document.get("results") or []:
        results.append(
            SearchResult(
                title=str(item.get("title", "")),
                url=str(item.get("url", "")),
                snippet=str(item.get("snippet", "") or item.get("content", "")),
            )
        )
    return results
