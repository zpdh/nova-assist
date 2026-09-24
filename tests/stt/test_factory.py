"""Tests for :func:`nova.stt.build_transcriber` and SttConfig."""

from __future__ import annotations

import pytest

from nova.stt import Transcriber, build_transcriber
from nova.stt.cli import WhisperCliTranscriber
from nova.stt.config import BACKEND_CLI, BACKEND_SERVER, SttConfig
from nova.stt.server import WhisperServerTranscriber


def test_factory_returns_server_transcriber():
    result = build_transcriber(SttConfig(backend=BACKEND_SERVER))

    assert isinstance(result, WhisperServerTranscriber)
    assert isinstance(result, Transcriber)


def test_factory_returns_cli_transcriber():
    result = build_transcriber(SttConfig(backend=BACKEND_CLI))

    assert isinstance(result, WhisperCliTranscriber)


def test_factory_rejects_unknown_backend():
    with pytest.raises(ValueError, match="unknown stt backend"):
        build_transcriber(SttConfig(backend="nope"))


def test_config_validated_rejects_unknown_backend():
    with pytest.raises(ValueError, match="unknown stt backend"):
        SttConfig(backend="nope").validated()
