"""Typed application configuration.

``WakeConfig`` is read from an optional TOML file (default: ``config.toml`` at
the repo root) and can be overridden by environment variables.

``LlmConfig`` is sourced entirely from environment variables (``NOVA_*``),
typically supplied via a local ``.env`` loaded by the caller/shell. It has no
built-in defaults: LLM settings are deployment-specific.

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
    """LLM settings for an OpenAI-compatible endpoint.

    All values come from environment variables; none have defaults.
    """

    base_url: str
    api_key: str
    model_fast: str | None = None
    model_smart: str | None = None


@dataclass(frozen=True)
class WakeConfig:
    """Wake-word detection settings."""

    phrase: str = "hey nova"


@dataclass(frozen=True)
class Config:
    """Top-level Nova configuration."""

    llm: LlmConfig
    wake: WakeConfig = field(default_factory=WakeConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Build a config from the TOML file and the environment.

        Args:
            path: TOML file to read. Defaults to ``config.toml`` at the repo
                root. Missing files are ignored.

        Raises:
            ValueError: if a required LLM environment variable is missing.
        """
        raw = _read_toml(path if path is not None else DEFAULT_CONFIG_PATH)
        wake_raw = raw.get("wake", {})

        wake = WakeConfig(
            phrase=_env("WAKE_PHRASE", _str_or(wake_raw, "phrase", WakeConfig.phrase)),
        )
        llm = LlmConfig(
            base_url=_required_env("LLM_BASE_URL"),
            api_key=_required_env("LLM_API_KEY"),
            model_fast=_optional_env("LLM_MODEL_FAST"),
            model_smart=_optional_env("LLM_MODEL_SMART"),
        )
        return cls(llm=llm, wake=wake)


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


def _env(suffix: str, default: str) -> str:
    """Return ``NOVA_<suffix>`` from the environment, else ``default``."""
    value = os.environ.get(ENV_PREFIX + suffix)
    return value if value not in (None, "") else default


def _required_env(suffix: str) -> str:
    """Return ``NOVA_<suffix>``, raising if unset or empty."""
    value = os.environ.get(ENV_PREFIX + suffix)
    if value in (None, ""):
        raise ValueError(f"missing required environment variable {ENV_PREFIX}{suffix}")
    return value


def _optional_env(suffix: str) -> str | None:
    """Return ``NOVA_<suffix>`` or ``None`` when unset/empty."""
    value = os.environ.get(ENV_PREFIX + suffix)
    return value if value not in (None, "") else None


__all__ = ["Config", "LlmConfig", "WakeConfig", "DEFAULT_CONFIG_PATH", "ENV_PREFIX"]
