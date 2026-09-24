"""Speech-to-text: turn audio files into text.

The public surface is the :class:`Transcriber` protocol and
:func:`build_transcriber`, which selects an implementation from config.
Backends keep whisper.cpp details private.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from nova.stt.config import BACKEND_CLI, BACKEND_SERVER, SttConfig
from nova.stt.errors import SttError, SttTimeout, SttUnavailable
from nova.stt.types import Segment, Transcript, Word


@runtime_checkable
class Transcriber(Protocol):
    """Transcribes a 16 kHz mono WAV file to text."""

    def transcribe(self, wav_path: Path) -> Transcript:
        """Return the transcription of ``wav_path``."""
        ...

    def close(self) -> None:
        """Release any resources (e.g. a resident server process)."""
        ...


def build_transcriber(config: SttConfig) -> Transcriber:
    """Construct the transcriber selected by ``config.backend``.

    Raises:
        ValueError: for an unknown backend.
    """
    # Imported lazily so importing nova.stt does not pull in subprocess/httpx.
    if config.backend == BACKEND_SERVER:
        from nova.stt.server import WhisperServerTranscriber

        return WhisperServerTranscriber(config)
    if config.backend == BACKEND_CLI:
        from nova.stt.cli import WhisperCliTranscriber

        return WhisperCliTranscriber(config)
    raise ValueError(f"unknown stt backend {config.backend!r}")


__all__ = [
    "Transcriber",
    "build_transcriber",
    "Transcript",
    "Segment",
    "Word",
    "SttConfig",
    "SttError",
    "SttUnavailable",
    "SttTimeout",
    "BACKEND_CLI",
    "BACKEND_SERVER",
]
