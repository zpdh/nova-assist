"""Tests for the store section of :func:`nova.config.Config.load`."""

from __future__ import annotations

from pathlib import Path

from nova.config import ENV_PREFIX, Config


def _clear_nova_env(monkeypatch) -> None:
    import os

    for key in [k for k in os.environ if k.startswith(ENV_PREFIX)]:
        monkeypatch.delenv(key, raising=False)


def _llm_env(monkeypatch) -> None:
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_API_KEY", "k")
    monkeypatch.setenv(f"{ENV_PREFIX}LLM_MODEL", "m")


def test_store_default_db_path(monkeypatch):
    _clear_nova_env(monkeypatch)
    _llm_env(monkeypatch)

    cfg = Config.load(path=Path("/nonexistent/config.toml"))

    assert cfg.store.db_path.name == "nova.db"
    assert cfg.store.db_path.parent.name == "data"


def test_store_toml_relative_path_resolves_against_config_dir(tmp_path, monkeypatch):
    _clear_nova_env(monkeypatch)
    _llm_env(monkeypatch)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[store]\ndb_path = "mydata/nova.db"\n')

    cfg = Config.load(path=cfg_file)

    assert cfg.store.db_path == tmp_path / "mydata" / "nova.db"


def test_store_env_overrides_toml(tmp_path, monkeypatch):
    _clear_nova_env(monkeypatch)
    _llm_env(monkeypatch)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[store]\ndb_path = "from_file.db"\n')
    override = tmp_path / "from_env.db"
    monkeypatch.setenv(f"{ENV_PREFIX}STORE_DB_PATH", str(override))

    cfg = Config.load(path=cfg_file)

    assert cfg.store.db_path == override
