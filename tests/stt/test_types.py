"""Tests for :mod:`nova.stt.types`."""

from __future__ import annotations

from nova.stt.types import Segment, Transcript, Word


def test_transcript_is_empty_for_whitespace():
    assert Transcript(text="   \n").is_empty
    assert Transcript(text="").is_empty
    assert not Transcript(text="hello").is_empty


def test_transcript_defaults_to_no_segments():
    assert Transcript(text="hi").segments == ()


def test_word_and_segment_are_frozen():
    word = Word(text="hi", start=0.0, end=0.5, probability=0.9)
    segment = Segment(text="hi", start=0.0, end=0.5, words=(word,))

    assert segment.words[0].probability == 0.9
    assert word.start == 0.0
