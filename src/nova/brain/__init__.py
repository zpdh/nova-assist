"""The brain: language model answers with optional web search.

The public surface is :func:`build_brain`, which wires a chat client, a model
router, and tool dispatchers from configuration. Callers use :class:`Brain`
only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova.brain.brain import Brain
from nova.brain.client import ChatClient
from nova.brain.errors import BrainError, BrainTimeout, BrainUnavailable
from nova.brain.router import ModelRouter, SingleModelRouter
from nova.brain.search import WebSearchClient
from nova.brain.tools import build_dispatchers
from nova.brain.types import ChatResult, Completion, Message, SearchResult, ToolCall

if TYPE_CHECKING:
    from nova.config import LlmConfig


def build_brain(config: LlmConfig) -> Brain:
    """Construct a :class:`Brain` from configuration."""
    client = ChatClient(config.base_url, config.api_key, config.model)
    search = WebSearchClient(config.base_url, config.api_key, config.search_provider)
    router: ModelRouter = SingleModelRouter(config.model)
    return Brain(client, router, build_dispatchers(search))


__all__ = [
    "Brain",
    "build_brain",
    "ChatClient",
    "Message",
    "ChatResult",
    "Completion",
    "SearchResult",
    "ToolCall",
    "ModelRouter",
    "SingleModelRouter",
    "BrainError",
    "BrainUnavailable",
    "BrainTimeout",
]
