"""Tests for :class:`nova.stt.cli.WhisperCliTranscriber`."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from nova.stt.cli import WhisperCliTranscriber
from nova.stt.config import BACKEND_CLI, SttConfig
from nova.stt.errors import SttError, SttUnavailable

# A fake whisper-cli that writes a canned JSON document to the -of prefix and
# exits with the code given by the FAKE_EXIT environment variable.
_FAKE_CLI = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
prefix = args[args.index("-of") + 1]
document = {
    "transcription": [
        {"text": " hey nova", "offsets": {"from": 0, "to": 1200}},
    ]
}
with open(prefix + ".json", "w") as fh:
    json.dump(document, fh)
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
"""


def _write_fake_cli(tmp_path: Path) -> Path:
    script = tmp_path / "fake-whisper-cli"
    script.write_text(_FAKE_CLI)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def _make_config(tmp_path: Path, binary: Path) -> SttConfig:
    model = tmp_path / "model.bin"
    model.write_bytes(b"fake")
    return SttConfig(backend=BACKEND_CLI, cli_path=binary, model_path=model)


def _write_wav(tmp_path: Path) -> Path:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"RIFF")
    return wav


def test_transcribes_via_fake_binary(tmp_path, monkeypatch):
    monkeypatch.delenv("FAKE_EXIT", raising=False)
    config = _make_config(tmp_path, _write_fake_cli(tmp_path))
    transcriber = WhisperCliTranscriber(config)

    result = transcriber.transcribe(_write_wav(tmp_path))

    assert result.text == " hey nova"
    assert result.segments[0].end == 1.2


def test_nonzero_exit_raises_stt_error(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_EXIT", "2")
    config = _make_config(tmp_path, _write_fake_cli(tmp_path))
    transcriber = WhisperCliTranscriber(config)

    with pytest.raises(SttError):
        transcriber.transcribe(_write_wav(tmp_path))


def test_missing_binary_raises_unavailable(tmp_path):
    config = _make_config(tmp_path, tmp_path / "nope")
    transcriber = WhisperCliTranscriber(config)

    with pytest.raises(SttUnavailable, match="binary not found"):
        transcriber.transcribe(_write_wav(tmp_path))


def test_missing_model_raises_unavailable(tmp_path):
    binary = _write_fake_cli(tmp_path)
    config = SttConfig(
        backend=BACKEND_CLI, cli_path=binary, model_path=tmp_path / "nope.bin"
    )
    transcriber = WhisperCliTranscriber(config)

    with pytest.raises(SttUnavailable, match="model file not found"):
        transcriber.transcribe(_write_wav(tmp_path))


def test_missing_audio_raises_unavailable(tmp_path):
    config = _make_config(tmp_path, _write_fake_cli(tmp_path))
    transcriber = WhisperCliTranscriber(config)

    with pytest.raises(SttUnavailable, match="audio file not found"):
        transcriber.transcribe(tmp_path / "missing.wav")


def test_cpu_device_appends_no_gpu_flag(tmp_path, monkeypatch):
    script = tmp_path / "fake-cli"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "open(os.environ['ARGS_FILE'], 'w').write(' '.join(sys.argv[1:]))\n"
        "args = sys.argv[1:]\n"
        "prefix = args[args.index('-of') + 1]\n"
        "open(prefix + '.json', 'w').write('{\"transcription\": []}')\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    args_file = tmp_path / "args.txt"
    monkeypatch.setenv("ARGS_FILE", str(args_file))

    model = tmp_path / "model.bin"
    model.write_bytes(b"fake")
    config = SttConfig(
        backend=BACKEND_CLI, cli_path=script, model_path=model, device="cpu"
    )

    WhisperCliTranscriber(config).transcribe(_write_wav(tmp_path))

    assert "-ng" in args_file.read_text().split()
