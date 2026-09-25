"""Value types for the store layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    """One conversation session."""

    id: str
    created_at: str
    updated_at: str


__all__ = ["Session"]
