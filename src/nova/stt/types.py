"""Value types returned by transcribers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Word:
    """A single recognized word with timing (seconds) and confidence."""

    text: str
    start: float
    end: float
    probability: float | None = None


@dataclass(frozen=True)
class Segment:
    """A contiguous span of transcription with timing (seconds)."""

    text: str
    start: float
    end: float
    words: tuple[Word, ...] = ()


@dataclass(frozen=True)
class Transcript:
    """The result of transcribing one audio file.

    ``text`` is the full transcription; ``segments``/``words`` are populated
    only when the backend was asked for verbose output.
    """

    text: str
    segments: tuple[Segment, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        """True when nothing was recognized."""
        return not self.text.strip()
