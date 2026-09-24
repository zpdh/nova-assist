"""Logging configuration for Nova.

A single :func:`setup_logging` entry point so every entry point (CLI, TUI,
background service) logs consistently. Kept dependency-free and idempotent.
"""

from __future__ import annotations

import logging
import os

DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DEFAULT_LEVEL = "INFO"

_configured = False


def setup_logging(level: str | int | None = None) -> None:
    """Configure the root logger once.

    The level is resolved from ``level`` argument, else ``NOVA_LOG_LEVEL``,
    else ``INFO``. Calling this more than once has no additional effect beyond
    updating the level.
    """
    global _configured

    resolved = _resolve_level(level)
    root = logging.getLogger()

    if _configured:
        root.setLevel(resolved)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
    root.addHandler(handler)
    root.setLevel(resolved)
    _configured = True


def _resolve_level(level: str | int | None) -> int:
    """Coerce a level name/number/env var into a logging level int."""
    if level is None:
        level = os.environ.get("NOVA_LOG_LEVEL", DEFAULT_LEVEL)
    if isinstance(level, int):
        return level
    return logging.getLevelName(level.upper())


__all__ = ["setup_logging", "DEFAULT_FORMAT", "DEFAULT_LEVEL"]
