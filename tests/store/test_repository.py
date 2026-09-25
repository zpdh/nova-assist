"""Tests for :mod:`nova.store.repository`."""

from __future__ import annotations

from nova.brain.types import Message
from nova.store.repository import Repository, SqliteRepository


def _repo() -> SqliteRepository:
    return SqliteRepository(":memory:")


def test_sqlite_repository_satisfies_protocol():
    assert isinstance(_repo(), Repository)


def test_create_session_generates_uuid7():
    repo = _repo()

    session_id = repo.create_session()

    assert session_id[14] == "7"  # uuid7 version nibble
    repo.close()


def test_create_session_accepts_explicit_id():
    repo = _repo()

    assert repo.create_session("fixed-id") == "fixed-id"
    repo.close()


def test_append_and_load_roundtrip():
    repo = _repo()
    session_id = repo.create_session()
    repo.append(session_id, Message(role="user", content="hi"))
    repo.append(session_id, Message(role="assistant", content="hello"))

    messages = repo.load(session_id)

    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "hi"
    repo.close()


def test_tool_calls_roundtrip_as_json():
    repo = _repo()
    session_id = repo.create_session()
    tool_calls = (
        {"id": "c1", "type": "function", "function": {"name": "web_search", "arguments": "{}"}},
    )
    repo.append(session_id, Message(role="assistant", content=None, tool_calls=tool_calls))

    loaded = repo.load(session_id)

    assert loaded[0].content is None
    assert loaded[0].tool_calls == tool_calls
    repo.close()


def test_append_all_preserves_order():
    repo = _repo()
    session_id = repo.create_session()
    messages = [
        Message(role="assistant", content=None, tool_calls=({"id": "c1"},)),
        Message(role="tool", content="result", tool_call_id="c1"),
        Message(role="assistant", content="final"),
    ]

    repo.append_all(session_id, messages)

    assert [m.role for m in repo.load(session_id)] == ["assistant", "tool", "assistant"]
    repo.close()


def test_load_unknown_session_is_empty():
    repo = _repo()

    assert repo.load("nope") == []
    repo.close()


def test_list_sessions_orders_by_id():
    repo = _repo()
    first = repo.create_session()
    second = repo.create_session()

    ids = [s.id for s in repo.list_sessions()]

    assert ids == sorted([first, second])
    repo.close()


def test_close_is_idempotent():
    repo = _repo()
    repo.close()
    repo.close()


def test_file_backed_repository_creates_parent_dir(tmp_path):
    db = tmp_path / "nested" / "nova.db"

    repo = SqliteRepository(db)
    repo.create_session()
    repo.close()

    assert db.is_file()
