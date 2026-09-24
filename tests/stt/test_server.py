"""Tests for :class:`nova.stt.server.WhisperServerTranscriber`.

These use a fake HTTP server and a fake binary, so no real model or GPU is
needed. The subprocess is replaced with a fake that simply sleeps.
"""

from __future__ import annotations

import json
import stat
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from nova.stt.config import BACKEND_SERVER, SttConfig
from nova.stt.errors import SttUnavailable
from nova.stt.server import WhisperServerTranscriber

_CANNED = {"text": " hey nova", "segments": [{"text": " hey nova", "start": 0.0, "end": 1.0}]}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # readiness probe
        self.send_response(200)
        self.end_headers()

    def do_POST(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = json.dumps(_CANNED).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence test output
        pass


@pytest.fixture
def fake_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


def _fake_server_binary(tmp_path: Path) -> Path:
    """A stand-in process that stays alive (it just sleeps)."""
    script = tmp_path / "fake-whisper-server"
    script.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(120)\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def _config(tmp_path: Path, binary: Path, port: int) -> SttConfig:
    model = tmp_path / "model.bin"
    model.write_bytes(b"fake")
    return SttConfig(backend=BACKEND_SERVER, server_path=binary, model_path=model, server_port=port)


def test_transcribes_against_running_server(tmp_path, fake_server):
    config = _config(tmp_path, _fake_server_binary(tmp_path), fake_server)
    transcriber = WhisperServerTranscriber(config)
    # Pretend the process is already running by pointing at the fake server.
    transcriber._process = _RunningStub()

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    result = transcriber.transcribe(wav)

    assert result.text == " hey nova"
    assert len(result.segments) == 1


def test_missing_audio_raises_unavailable(tmp_path):
    config = _config(tmp_path, _fake_server_binary(tmp_path), 18000)
    transcriber = WhisperServerTranscriber(config)

    with pytest.raises(SttUnavailable, match="audio file not found"):
        transcriber.transcribe(tmp_path / "missing.wav")


def test_missing_binary_raises_unavailable(tmp_path):
    config = _config(tmp_path, tmp_path / "nope", 18000)
    transcriber = WhisperServerTranscriber(config)

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(SttUnavailable, match="binary not found"):
        transcriber.transcribe(wav)


def test_missing_model_raises_unavailable(tmp_path):
    binary = _fake_server_binary(tmp_path)
    config = SttConfig(backend=BACKEND_SERVER, server_path=binary, model_path=tmp_path / "nope.bin")
    transcriber = WhisperServerTranscriber(config)

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(SttUnavailable, match="model file not found"):
        transcriber.transcribe(wav)


def test_close_is_safe_when_never_started(tmp_path):
    config = _config(tmp_path, _fake_server_binary(tmp_path), 18000)
    WhisperServerTranscriber(config).close()  # must not raise


def test_context_manager_closes(tmp_path):
    config = _config(tmp_path, _fake_server_binary(tmp_path), 18000)
    with WhisperServerTranscriber(config) as transcriber:
        assert transcriber._process is None
    assert transcriber._process is None


class _RunningStub:
    """Minimal stand-in for a live subprocess.Popen."""

    pid = 12345

    def poll(self):
        return None
