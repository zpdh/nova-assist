"""Opt-in integration tests against the real whisper.cpp build.

Skipped by default. Run with:

    pytest -m integration

Requires the in-repo Virt build and model, plus an audio clip. This exercises
the real binary/server, GPU, and parsing end to end.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nova.stt import build_transcriber
from nova.stt.config import BACKEND_CLI, BACKEND_SERVER, SttConfig

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WAV = _REPO_ROOT / "tmp" / "nova_pickup_test.wav"
_MODEL = _REPO_ROOT / "models" / "ggml-tiny.en.bin"


def _skip_unless_ready() -> None:
    if not _WAV.is_file():
        pytest.skip(f"test clip not found: {_WAV}")
    if not _MODEL.is_file():
        pytest.skip(f"model not found: {_MODEL}")


@pytest.mark.parametrize("backend", [BACKEND_CLI, BACKEND_SERVER])
def test_transcribes_real_clip(backend):
    _skip_unless_ready()
    transcriber = build_transcriber(SttConfig(backend=backend))
    try:
        result = transcriber.transcribe(_WAV)
    finally:
        transcriber.close()

    assert not result.is_empty
    assert "nova" in result.text.lower()
