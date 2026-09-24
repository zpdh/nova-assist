"""Errors raised by the brain (language model + tools) layer."""

from __future__ import annotations


class BrainError(Exception):
    """Base class for brain failures."""


class BrainUnavailable(BrainError):
    """The configured language model endpoint cannot be used."""


class BrainTimeout(BrainError):
    """A request to the language model or a tool did not complete in time."""
