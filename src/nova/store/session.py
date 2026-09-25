"""Session service: composes the brain and the repository.

The service owns conversation policy: it loads history, prepends the system
prompt, asks the brain, and persists the user message plus the turns the brain
generated. The brain stays stateless.
"""

from __future__ import annotations

import logging

from nova.brain.brain import Brain
from nova.brain.types import Message
from nova.store.repository import Repository

log = logging.getLogger(__name__)


class Session:
    """One ongoing conversation backed by a store session."""

    def __init__(
        self,
        session_id: str,
        brain: Brain,
        repository: Repository,
        system_prompt: str,
    ) -> None:
        self._session_id = session_id
        self._brain = brain
        self._repository = repository
        self._system_prompt = system_prompt

    @property
    def id(self) -> str:
        return self._session_id

    def messages(self) -> list[Message]:
        """Return the stored conversation history (without the system prompt)."""
        return self._repository.load(self._session_id)

    def ask(self, text: str) -> str:
        """Answer ``text`` in this session and persist the new turns."""
        user = Message(role="user", content=text)
        messages = [
            Message(role="system", content=self._system_prompt),
            *self.messages(),
            user,
        ]
        result = self._brain.chat(messages)

        self._repository.append(self._session_id, user)
        self._repository.append_all(self._session_id, list(result.turns))
        return result.text


def open_session(
    repository: Repository,
    brain: Brain,
    system_prompt: str,
    session_id: str | None = None,
) -> Session:
    """Return a :class:`Session`, creating it in the store if it does not exist."""
    known = {session.id for session in repository.list_sessions()}
    if session_id is None or session_id not in known:
        session_id = repository.create_session(session_id)
    return Session(session_id, brain, repository, system_prompt)


__all__ = ["Session", "open_session"]
