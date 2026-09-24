"""Errors raised by the speech-to-text layer."""

from __future__ import annotations


class SttError(Exception):
    """Base class for speech-to-text failures."""


class SttUnavailable(SttError):
    """The configured speech-to-text backend cannot be used.

    Raised when the binary or model is missing, or a server cannot start.
    """


class SttTimeout(SttError):
    """A transcription request did not complete in time."""
