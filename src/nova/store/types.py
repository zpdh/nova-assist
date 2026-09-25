"""Value types for the store layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionInfo:
    """One stored conversation session (metadata only)."""

    id: str
    created_at: str
    updated_at: str


__all__ = ["SessionInfo"]
