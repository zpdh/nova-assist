"""Tests for :mod:`nova.stt.parsing`."""

from __future__ import annotations

from nova.stt.parsing import parse_cli_document, parse_response


def test_parse_simple_response():
    result = parse_response({"text": " hello world"})

    assert result.text == " hello world"
    assert result.segments == ()


def test_parse_verbose_response_with_words():
    payload = {
        "text": "hey nova",
        "segments": [
            {
                "text": "hey nova",
                "start": 0.0,
                "end": 1.2,
                "words": [
                    {"word": " hey", "start": 0.0, "end": 0.4, "probability": 0.9},
                    {"word": " nova", "start": 0.5, "end": 1.0, "probability": 0.8},
                ],
            }
        ],
    }

    result = parse_response(payload)

    assert result.text == "hey nova"
    assert len(result.segments) == 1
    segment = result.segments[0]
    assert segment.start == 0.0
    assert segment.end == 1.2
    assert [w.text for w in segment.words] == [" hey", " nova"]
    assert segment.words[1].probability == 0.8


def test_parse_word_without_probability():
    payload = {
        "text": "x",
        "segments": [{"text": "x", "start": 0.0, "end": 1.0, "words": [{"word": " x"}]}],
    }

    result = parse_response(payload)

    assert result.segments[0].words[0].probability is None


def test_parse_cli_document_joins_text_and_converts_offsets():
    document = {
        "transcription": [
            {"text": " hello", "offsets": {"from": 0, "to": 1500}},
            {"text": " world", "offsets": {"from": 1500, "to": 3000}},
        ]
    }

    result = parse_cli_document(document)

    assert result.text == " hello world"
    assert result.segments[0].start == 0.0
    assert result.segments[0].end == 1.5
    assert result.segments[1].start == 1.5


def test_parse_cli_document_handles_missing_offsets():
    result = parse_cli_document({"transcription": [{"text": " hi"}]})

    assert result.text == " hi"
    assert result.segments[0].start == 0.0
    assert result.segments[0].end == 0.0


def test_parse_response_tolerates_empty_payload():
    result = parse_response({})

    assert result.text == ""
    assert result.is_empty
