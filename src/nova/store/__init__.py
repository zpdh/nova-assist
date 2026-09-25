"""Conversation persistence: sessions and messages in SQLite.

The public surface is :func:`build_store` (a factory for the repository) and
:func:`open_session` (which composes the repository with the brain). Callers
depend on the :class:`Repository` protocol, not on SQLite.
"""

from __future__ import annotations

from nova.store.config import StoreConfig
from nova.store.repository import Repository, SqliteRepository
from nova.store.session import Session, open_session
from nova.store.types import SessionInfo


def build_store(config: StoreConfig) -> Repository:
    """Construct a :class:`Repository` from configuration."""
    return SqliteRepository(config.db_path)


__all__ = [
    "build_store",
    "Repository",
    "SqliteRepository",
    "Session",
    "SessionInfo",
    "open_session",
    "StoreConfig",
]
