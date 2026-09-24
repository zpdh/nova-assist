"""Configuration for the brain layer.

Values come from the ``[brain]`` section of ``config.toml`` and can be
overridden by ``NOVA_BRAIN_*`` environment variables.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SYSTEM_PROMPT = (
    "You are Nova, a concise voice assistant. Answer briefly and directly. "
    "Use the web_search tool when the answer needs current or verifiable facts."
)


@dataclass(frozen=True)
class BrainConfig:
    """Settings for the brain."""

    system_prompt: str = DEFAULT_SYSTEM_PROMPT


__all__ = ["BrainConfig", "DEFAULT_SYSTEM_PROMPT"]
