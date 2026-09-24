"""Typed application configuration.

Precedence (lowest to highest):

1. Built-in defaults (the dataclass field defaults).
2. Values from a TOML file (default: ``config.toml`` at the repo root).
3. Environment variables (``NOVA_*``), typically supplied via a local ``.env``
   that is loaded by the caller/shell.

Secrets must never live in the TOML file; they come from the environment.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ENV_PREFIX = "NOVA_"

# Repo root = two levels up from this file (src/nova/config.py -> repo root).
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"


@dataclass(frozen=True)
class LlmConfig:
    """LLM / search gateway settings (9Router, OpenAI-compatible)."""

    base_url: str = "http://localhost:20128/v1"
    api_key: str = ""
    model_fast: str = ""
    model_smart: str = ""


@dataclass(frozen=True)
class WakeConfig:
    """Wake-word detection settings."""

    phrase: str = "hey nova"


@dataclass(frozen=True)
class Config:
    """Top-level Nova configuration."""

    wake: WakeConfig = field(default_factory=WakeConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Build a config from defaults, an optional TOML file, and the env.

        Args:
            path: TOML file to read. Defaults to ``config.toml`` at the repo
                root. Missing files are ignored (defaults + env still apply).
        """
        raw = _read_toml(path if path is not None else DEFAULT_CONFIG_PATH)
        wake_raw = raw.get("wake", {})
        llm_raw = raw.get("llm", {})

        wake = WakeConfig(
            phrase=_env_str("WAKE_PHRASE", _str_or(wake_raw, "phrase", WakeConfig.phrase)),
        )
        llm = LlmConfig(
            base_url=_env_str("LLM_BASE_URL", _str_or(llm_raw, "base_url", LlmConfig.base_url)),
            api_key=_env_str("LLM_API_KEY", _str_or(llm_raw, "api_key", LlmConfig.api_key)),
            model_fast=_env_str(
                "LLM_MODEL_FAST", _str_or(llm_raw, "model_fast", LlmConfig.model_fast)
            ),
            model_smart=_env_str(
                "LLM_MODEL_SMART", _str_or(llm_raw, "model_smart", LlmConfig.model_smart)
            ),
        )
        return cls(wake=wake, llm=llm)


def _read_toml(path: Path) -> dict:
    """Read a TOML file, returning an empty dict if it does not exist."""
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _str_or(section: dict, key: str, default: str) -> str:
    """Read ``section[key]`` as a str, falling back to ``default``."""
    value = section.get(key, default)
    return str(value) if value is not None else default


def _env_str(suffix: str, default: str) -> str:
    """Return ``NOVA_<suffix>`` from the environment, else ``default``."""
    value = os.environ.get(ENV_PREFIX + suffix)
    return value if value not in (None, "") else default


__all__ = ["Config", "LlmConfig", "WakeConfig", "DEFAULT_CONFIG_PATH", "ENV_PREFIX"]
