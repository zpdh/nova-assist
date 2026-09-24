"""Tests for :mod:`nova.config` precedence and parsing."""

from __future__ import annotations

from pathlib import Path

from nova.config import ENV_PREFIX, Config


def test_defaults_when_no_file_and_no_env(monkeypatch):
    # Ensure no NOVA_* env leaks in from the test runner environment.
    for key in list(_nova_env_keys()):
        monkeypatch.delenv(key, raising=False)

    cfg = Config.load(path=Path("/nonexistent/config.toml"))

    assert cfg.wake.phrase == "hey nova"
    assert cfg.llm.base_url == "http://localhost:20128/v1"
    assert cfg.llm.api_key == ""


def test_toml_overrides_defaults(tmp_path: Path, monkeypatch):
    for key in list(_nova_env_keys()):
        monkeypatch.delenv(key, raising=False)

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        "[wake]\n"
        'phrase = "oi nova"\n'
        "[llm]\n"
        'base_url = "http://example.test/v1"\n'
        'model_fast = "small-model"\n'
    )

    cfg = Config.load(path=cfg_file)

    assert cfg.wake.phrase == "oi nova"
    assert cfg.llm.base_url == "http://example.test/v1"
    assert cfg.llm.model_fast == "small-model"


def test_env_overrides_toml(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[llm]\nbase_url = "http://from-file/v1"\n')

    monkeypatch.setenv(f"{ENV_PREFIX}LLM_BASE_URL", "http://from-env/v1")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "secret")
    monkeypatch.setenv(f"{ENV_PREFIX}WAKE_PHRASE", "hey override")

    cfg = Config.load(path=cfg_file)

    assert cfg.llm.base_url == "http://from-env/v1"
    assert cfg.llm.api_key == "secret"
    assert cfg.wake.phrase == "hey override"


def test_empty_env_value_falls_back_to_default(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_BASE_URL", "")

    cfg = Config.load(path=tmp_path / "missing.toml")

    assert cfg.llm.base_url == "http://localhost:20128/v1"


def _nova_env_keys():
    import os

    return [k for k in os.environ if k.startswith(ENV_PREFIX)]
