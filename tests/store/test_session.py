"""Tests for :mod:`nova.store.session`."""

from __future__ import annotations

from nova.brain.types import ChatResult, Message
from nova.store.repository import SqliteRepository
from nova.store.session import Session, open_session


class FakeBrain:
    """A brain that returns a fixed reply and records the messages it saw."""

    def __init__(self, reply: str = "answer") -> None:
        self.reply = reply
        self.seen: list[list[Message]] = []

    def chat(self, messages: list[Message]) -> ChatResult:
        self.seen.append(messages)
        return ChatResult(text=self.reply, turns=(Message(role="assistant", content=self.reply),))

    def close(self) -> None:  # pragma: no cover - parity with Brain
        pass


def _session(repo: SqliteRepository, brain: FakeBrain, session_id: str | None = None) -> Session:
    return open_session(repo, brain, "SYS", session_id)


def test_open_session_creates_when_missing():
    repo = SqliteRepository(":memory:")
    session = _session(repo, FakeBrain())

    assert session.id in [s.id for s in repo.list_sessions()]
    repo.close()


def test_ask_returns_brain_text():
    repo = SqliteRepository(":memory:")
    brain = FakeBrain("hi there")
    session = _session(repo, brain, "s1")

    assert session.ask("hello") == "hi there"
    repo.close()


def test_ask_prepends_system_prompt():
    repo = SqliteRepository(":memory:")
    brain = FakeBrain()
    session = _session(repo, brain, "s1")

    session.ask("hello")

    first = brain.seen[0]
    assert first[0].role == "system"
    assert first[0].content == "SYS"
    assert first[-1].content == "hello"
    repo.close()


def test_ask_persists_user_and_turns():
    repo = SqliteRepository(":memory:")
    session = _session(repo, FakeBrain("reply"), "s1")

    session.ask("q")

    roles = [m.role for m in session.messages()]
    assert roles == ["user", "assistant"]
    repo.close()


def test_second_ask_replays_history():
    repo = SqliteRepository(":memory:")
    brain = FakeBrain()
    session = _session(repo, brain, "s1")

    session.ask("first")
    session.ask("second")

    second_call = brain.seen[1]
    # system + history(user, assistant) + new user
    assert [m.role for m in second_call] == ["system", "user", "assistant", "user"]
    repo.close()


def test_reopening_session_loads_history():
    repo = SqliteRepository(":memory:")
    _session(repo, FakeBrain("one"), "s1").ask("hello")

    reopened = _session(repo, FakeBrain("two"), "s1")
    brain = reopened._brain  # noqa: SLF001 (test inspects the fake)
    reopened.ask("again")

    assert [m.role for m in reopened.messages()] == ["user", "assistant", "user", "assistant"]
    assert [m.content for m in brain.seen[0]][-1] == "again"
    repo.close()


def test_open_session_reuses_existing_id():
    repo = SqliteRepository(":memory:")
    _session(repo, FakeBrain(), "s1")

    session = _session(repo, FakeBrain(), "s1")

    assert len(repo.list_sessions()) == 1
    assert session.id == "s1"
    repo.close()
