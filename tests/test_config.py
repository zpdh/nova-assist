"""Tests for :mod:`nova.config` precedence and parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from nova.config import ENV_PREFIX, Config


def _clear_nova_env(monkeypatch) -> None:
    import os

    for key in [k for k in os.environ if k.startswith(ENV_PREFIX)]:
        monkeypatch.delenv(key, raising=False)


def _set_llm_env(monkeypatch) -> None:
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "secret")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_MODEL", "my-model")


def test_wake_defaults_when_no_file(monkeypatch):
    _clear_nova_env(monkeypatch)
    _set_llm_env(monkeypatch)

    cfg = Config.load(path=Path("/nonexistent/config.toml"))

    assert cfg.wake.phrase == "hey nova"


def test_toml_overrides_wake_default(tmp_path: Path, monkeypatch):
    _clear_nova_env(monkeypatch)
    _set_llm_env(monkeypatch)

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[wake]\nphrase = "oi nova"\n')

    cfg = Config.load(path=cfg_file)

    assert cfg.wake.phrase == "oi nova"


def test_env_overrides_toml_wake(tmp_path: Path, monkeypatch):
    _clear_nova_env(monkeypatch)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[wake]\nphrase = "from file"\n')

    _set_llm_env(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}WAKE_PHRASE", "hey override")

    cfg = Config.load(path=cfg_file)

    assert cfg.wake.phrase == "hey override"


def test_llm_reads_from_env(monkeypatch):
    _clear_nova_env(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "secret")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_MODEL", "my-model")

    cfg = Config.load(env_file=None)

    assert cfg.llm.api_key == "secret"
    assert cfg.llm.model == "my-model"
    # base_url and search_provider have defaults.
    assert cfg.llm.base_url == "http://localhost:20128/v1"
    assert cfg.llm.search_provider == "tavily"


def test_llm_base_url_and_provider_override(monkeypatch):
    _clear_nova_env(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "secret")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_MODEL", "my-model")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_BASE_URL", "http://env-only/v1")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_SEARCH_PROVIDER", "brave")

    cfg = Config.load(env_file=None)

    assert cfg.llm.base_url == "http://env-only/v1"
    assert cfg.llm.search_provider == "brave"


def test_missing_required_llm_env_raises(monkeypatch):
    _clear_nova_env(monkeypatch)

    # env_file=None so the developer's real .env does not leak into the test.
    with pytest.raises(ValueError, match="NOVA_LLM_API_KEY"):
        Config.load(env_file=None)

    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "secret")

    with pytest.raises(ValueError, match="NOVA_LLM_MODEL"):
        Config.load(env_file=None)


def test_brain_system_prompt_default(monkeypatch):
    _clear_nova_env(monkeypatch)
    _set_llm_env(monkeypatch)

    cfg = Config.load(path=Path("/nonexistent/config.toml"))

    assert "Nova" in cfg.brain.system_prompt


def test_env_file_loaded_when_present(tmp_path, monkeypatch):
    _clear_nova_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment\n\nNOVA_LLM_API_KEY="from-dotenv"\nNOVA_LLM_MODEL=dotenv-model\n'
    )

    cfg = Config.load(path=tmp_path / "config.toml", env_file=env_file)

    assert cfg.llm.api_key == "from-dotenv"
    assert cfg.llm.model == "dotenv-model"


def test_env_file_does_not_override_real_env(tmp_path, monkeypatch):
    _clear_nova_env(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "real-env")
    env_file = tmp_path / ".env"
    env_file.write_text("NOVA_LLM_API_KEY=from-dotenv\nNOVA_LLM_MODEL=dotenv-model\n")

    cfg = Config.load(path=tmp_path / "config.toml", env_file=env_file)

    assert cfg.llm.api_key == "real-env"


def test_env_file_missing_is_noop(tmp_path, monkeypatch):
    _clear_nova_env(monkeypatch)
    _set_llm_env(monkeypatch)

    cfg = Config.load(path=tmp_path / "config.toml", env_file=tmp_path / "absent.env")

    assert cfg.llm.api_key == "secret"


def test_env_file_auto_reads_next_to_config(tmp_path, monkeypatch):
    _clear_nova_env(monkeypatch)
    (tmp_path / ".env").write_text("NOVA_LLM_API_KEY=auto-key\nNOVA_LLM_MODEL=auto-model\n")

    cfg = Config.load(path=tmp_path / "config.toml")  # env_file defaults to "auto"

    assert cfg.llm.api_key == "auto-key"
    assert cfg.llm.model == "auto-model"


def test_brain_system_prompt_from_toml(tmp_path: Path, monkeypatch):
    _clear_nova_env(monkeypatch)
    _set_llm_env(monkeypatch)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[brain]\nsystem_prompt = "Be terse."\n')

    cfg = Config.load(path=cfg_file)

    assert cfg.brain.system_prompt == "Be terse."


def test_brain_system_prompt_env_override(monkeypatch):
    _clear_nova_env(monkeypatch)
    _set_llm_env(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}BRAIN_SYSTEM_PROMPT", "env prompt")

    cfg = Config.load(path=Path("/nonexistent/config.toml"))

    assert cfg.brain.system_prompt == "env prompt"
