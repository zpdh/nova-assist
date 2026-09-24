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

from nova.stt import server as server_mod
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


def test_http_client_is_reused_across_calls(tmp_path, fake_server):
    config = _config(tmp_path, _fake_server_binary(tmp_path), fake_server)
    transcriber = WhisperServerTranscriber(config)
    transcriber._process = _RunningStub()
    client = transcriber._client

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    transcriber.transcribe(wav)
    transcriber.transcribe(wav)

    assert transcriber._client is client
    assert not client.is_closed


def test_close_closes_http_client(tmp_path):
    config = _config(tmp_path, _fake_server_binary(tmp_path), 18000)
    transcriber = WhisperServerTranscriber(config)
    client = transcriber._client

    transcriber.close()

    assert client.is_closed
    transcriber.close()  # idempotent


def test_retries_with_new_port_on_startup_failure(tmp_path, fake_server, monkeypatch):
    config = _config(tmp_path, _fake_server_binary(tmp_path), fake_server)
    transcriber = WhisperServerTranscriber(config)

    ports_tried: list[int] = []
    real_free_port = server_mod._free_port

    def tracking_free_port(preferred, host):
        port = real_free_port(preferred, host) if not ports_tried else 0
        ports_tried.append(port)
        return port

    monkeypatch.setattr(server_mod, "_free_port", tracking_free_port)

    # First readiness wait fails, second succeeds.
    attempts = {"n": 0}

    def flaky_wait():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise server_mod._StartupFailed("simulated port collision")
        # Second attempt succeeds; point at the real fake server for the request.
        transcriber._port = fake_server

    monkeypatch.setattr(transcriber, "_wait_until_ready", flaky_wait)
    monkeypatch.setattr(transcriber, "_start_process", lambda: None)

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    result = transcriber.transcribe(wav)

    assert result.text == " hey nova"
    assert attempts["n"] == 2
    assert len(ports_tried) == 2
    assert ports_tried[0] != ports_tried[1]


def test_does_not_retry_on_non_startup_error(tmp_path, monkeypatch):
    config = _config(tmp_path, tmp_path / "nope", 18000)
    transcriber = WhisperServerTranscriber(config)

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")

    # Missing binary raises SttUnavailable (not _StartupFailed) -> no retry.
    with pytest.raises(SttUnavailable, match="binary not found"):
        transcriber.transcribe(wav)


def test_all_attempts_failing_raises_unavailable(tmp_path, monkeypatch):
    config = _config(tmp_path, _fake_server_binary(tmp_path), 18000)
    transcriber = WhisperServerTranscriber(config)

    monkeypatch.setattr(transcriber, "_start_process", lambda: None)

    def always_fail():
        raise server_mod._StartupFailed("simulated")

    monkeypatch.setattr(transcriber, "_wait_until_ready", always_fail)

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(SttUnavailable, match="after 3 attempts"):
        transcriber.transcribe(wav)
