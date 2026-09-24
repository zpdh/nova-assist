"""Tests for :mod:`nova.config` precedence and parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from nova.config import ENV_PREFIX, Config


def _clear_nova_env(monkeypatch) -> None:
    import os

    for key in [k for k in os.environ if k.startswith(ENV_PREFIX)]:
        monkeypatch.delenv(key, raising=False)


def test_wake_defaults_when_no_file(monkeypatch):
    _clear_nova_env(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_BASE_URL", "http://example.test/v1")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "secret")

    cfg = Config.load(path=Path("/nonexistent/config.toml"))

    assert cfg.wake.phrase == "hey nova"


def test_toml_overrides_wake_default(tmp_path: Path, monkeypatch):
    _clear_nova_env(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_BASE_URL", "http://example.test/v1")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "secret")

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[wake]\nphrase = "oi nova"\n')

    cfg = Config.load(path=cfg_file)

    assert cfg.wake.phrase == "oi nova"


def test_env_overrides_toml_wake(tmp_path: Path, monkeypatch):
    _clear_nova_env(monkeypatch)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[wake]\nphrase = "from file"\n')

    monkeypatch.setenv(f"{ENV_PREFIX}LLM_BASE_URL", "http://example.test/v1")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "secret")
    monkeypatch.setenv(f"{ENV_PREFIX}WAKE_PHRASE", "hey override")

    cfg = Config.load(path=cfg_file)

    assert cfg.wake.phrase == "hey override"


def test_llm_reads_from_env(monkeypatch):
    _clear_nova_env(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_BASE_URL", "http://env-only/v1")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "secret")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_MODEL_FAST", "fast")

    cfg = Config.load()

    assert cfg.llm.base_url == "http://env-only/v1"
    assert cfg.llm.api_key == "secret"
    assert cfg.llm.model_fast == "fast"
    # Unset optional model is None, not empty string.
    assert cfg.llm.model_smart is None


def test_missing_required_llm_env_raises(monkeypatch):
    _clear_nova_env(monkeypatch)

    with pytest.raises(ValueError, match="NOVA_LLM_BASE_URL"):
        Config.load()

    monkeypatch.setenv(f"{ENV_PREFIX}LLM_BASE_URL", "http://example.test/v1")

    with pytest.raises(ValueError, match="NOVA_LLM_API_KEY"):
        Config.load()
