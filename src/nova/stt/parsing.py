"""Parsing of whisper.cpp JSON output into :mod:`nova.stt.types`.

Both backends consume OpenAI-style JSON:

- ``{"text": "..."}``                             (``response_format=json``)
- ``{"text": "...", "segments": [...]}``         (``response_format=verbose_json``)

The ``whisper-cli`` JSON file wraps the same shape under ``transcription``.
This module centralizes the field access so the backends stay thin.
"""

from __future__ import annotations

from typing import Any

from nova.stt.types import Segment, Transcript, Word


def parse_response(payload: dict[str, Any]) -> Transcript:
    """Build a :class:`Transcript` from an OpenAI-style response object."""
    text = str(payload.get("text", ""))
    raw_segments = payload.get("segments") or []
    segments = tuple(_parse_segment(seg) for seg in raw_segments)
    return Transcript(text=text, segments=segments)


def parse_cli_document(document: dict[str, Any]) -> Transcript:
    """Build a :class:`Transcript` from ``whisper-cli``'s JSON document.

    The cli writes ``{"transcription": [{"text": ..., "offsets": {...}}]}``.
    """
    entries = document.get("transcription") or []
    segments: list[Segment] = []
    texts: list[str] = []

    for entry in entries:
        text = str(entry.get("text", ""))
        texts.append(text)
        offsets = entry.get("offsets") or {}
        # cli offsets are milliseconds; Segment timing is seconds.
        start = _to_seconds(offsets.get("from"))
        end = _to_seconds(offsets.get("to"))
        segments.append(Segment(text=text, start=start, end=end))

    return Transcript(text="".join(texts), segments=tuple(segments))


def _parse_segment(raw: dict[str, Any]) -> Segment:
    words = tuple(_parse_word(w) for w in (raw.get("words") or []))
    return Segment(
        text=str(raw.get("text", "")),
        start=float(raw.get("start", 0.0)),
        end=float(raw.get("end", 0.0)),
        words=words,
    )


def _parse_word(raw: dict[str, Any]) -> Word:
    prob = raw.get("probability")
    return Word(
        text=str(raw.get("word", raw.get("text", ""))),
        start=float(raw.get("start", 0.0)),
        end=float(raw.get("end", 0.0)),
        probability=float(prob) if prob is not None else None,
    )


def _to_seconds(value: Any) -> float:
    """Convert a millisecond offset to seconds, tolerating ``None``."""
    if value is None:
        return 0.0
    return float(value) / 1000.0
