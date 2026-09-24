"""Tests for the stt section of :func:`nova.config.Config.load`."""

from __future__ import annotations

from pathlib import Path

from nova.config import ENV_PREFIX, Config
from nova.stt.config import BACKEND_CLI


def _clear_nova_env(monkeypatch) -> None:
    import os

    for key in [k for k in os.environ if k.startswith(ENV_PREFIX)]:
        monkeypatch.delenv(key, raising=False)


def _llm_env(monkeypatch) -> None:
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "k")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_MODEL", "m")


def test_stt_defaults(monkeypatch):
    _clear_nova_env(monkeypatch)
    _llm_env(monkeypatch)

    cfg = Config.load(path=Path("/nonexistent/config.toml"))

    assert cfg.stt.backend == "server"
    assert cfg.stt.model_path.name == "ggml-tiny.en.bin"


def test_stt_toml_section(tmp_path, monkeypatch):
    _clear_nova_env(monkeypatch)
    _llm_env(monkeypatch)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[stt]\nbackend = "cli"\nmodel_path = "models/custom.bin"\nthreads = 8\n')

    cfg = Config.load(path=cfg_file)

    assert cfg.stt.backend == BACKEND_CLI
    assert cfg.stt.threads == 8
    # Relative path resolved against the config file's directory.
    assert cfg.stt.model_path == tmp_path / "models" / "custom.bin"


def test_stt_env_overrides_toml(tmp_path, monkeypatch):
    _clear_nova_env(monkeypatch)
    _llm_env(monkeypatch)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[stt]\nbackend = "cli"\n')
    monkeypatch.setenv(f"{ENV_PREFIX}STT_BACKEND", "server")
    monkeypatch.setenv(f"{ENV_PREFIX}STT_THREADS", "12")

    cfg = Config.load(path=cfg_file)

    assert cfg.stt.backend == "server"
    assert cfg.stt.threads == 12
