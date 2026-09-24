"""Model selection.

A :class:`ModelRouter` chooses which configured model handles a request. The
single implementation returns the one configured model; a future implementation
may route between fast and smart models. This is a Strategy: the brain depends
on the interface, so the selection policy can change without touching the brain.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ModelRouter(Protocol):
    """Chooses the model id to use for a request."""

    def choose(self, messages: list[dict]) -> str:
        """Return the model id for the given conversation."""
        ...


class SingleModelRouter:
    """Always returns the same configured model."""

    def __init__(self, model: str) -> None:
        if not model:
            raise ValueError("model must not be empty")
        self._model = model

    def choose(self, messages: list[dict]) -> str:  # noqa: ARG002 (interface)
        return self._model


__all__ = ["ModelRouter", "SingleModelRouter"]
