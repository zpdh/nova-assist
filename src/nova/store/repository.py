"""Persistence for conversations.

A :class:`Repository` hides SQLite behind a collection-like interface: create
sessions, append messages, and read them back as :class:`Message` values. This
lets other code store and load history without knowing the database.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from nova.brain.types import Message
from nova.store import schema
from nova.store.types import Session

log = logging.getLogger(__name__)


@runtime_checkable
class Repository(Protocol):
    """Stores and loads conversation sessions and messages."""

    def create_session(self, session_id: str | None = None) -> str: ...

    def append(self, session_id: str, message: Message) -> None: ...

    def append_all(self, session_id: str, messages: list[Message]) -> None: ...

    def load(self, session_id: str) -> list[Message]: ...

    def list_sessions(self) -> list[Session]: ...

    def close(self) -> None: ...


class SqliteRepository:
    """A :class:`Repository` backed by a SQLite file."""

    def __init__(self, db_path: Path | str) -> None:
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(db_path))
        self._connection.row_factory = sqlite3.Row
        schema.initialize(self._connection)

    def create_session(self, session_id: str | None = None) -> str:
        """Create a session and return its id (a uuid7 when none is given)."""
        session_id = session_id or str(uuid.uuid7())
        now = _now()
        self._connection.execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)",
            (session_id, now, now),
        )
        self._connection.commit()
        return session_id

    def append(self, session_id: str, message: Message) -> None:
        """Append one message to a session."""
        self._connection.execute(
            """
            INSERT INTO messages
                (session_id, role, content, tool_calls, tool_call_id, name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                message.role,
                message.content,
                _encode_tool_calls(message.tool_calls),
                message.tool_call_id,
                message.name,
                _now(),
            ),
        )
        self._connection.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id)
        )
        self._connection.commit()

    def append_all(self, session_id: str, messages: list[Message]) -> None:
        """Append several messages to a session."""
        for message in messages:
            self.append(session_id, message)

    def load(self, session_id: str) -> list[Message]:
        """Return a session's messages in insertion order."""
        rows = self._connection.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
        return [_row_to_message(row) for row in rows]

    def list_sessions(self) -> list[Session]:
        """Return all sessions, oldest first (uuid7 ids sort by time)."""
        rows = self._connection.execute(
            "SELECT id, created_at, updated_at FROM sessions ORDER BY id"
        ).fetchall()
        return [
            Session(id=row["id"], created_at=row["created_at"], updated_at=row["updated_at"])
            for row in rows
        ]

    def close(self) -> None:
        """Close the database connection (idempotent)."""
        self._connection.close()

    def __enter__(self) -> SqliteRepository:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _row_to_message(row: sqlite3.Row) -> Message:
    return Message(
        role=row["role"],
        content=row["content"],
        tool_calls=_decode_tool_calls(row["tool_calls"]),
        tool_call_id=row["tool_call_id"],
        name=row["name"],
    )


def _encode_tool_calls(tool_calls: tuple[dict, ...]) -> str | None:
    if not tool_calls:
        return None
    return json.dumps(list(tool_calls))


def _decode_tool_calls(raw: str | None) -> tuple[dict, ...]:
    if not raw:
        return ()
    return tuple(json.loads(raw))


def _now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = ["Repository", "SqliteRepository"]
