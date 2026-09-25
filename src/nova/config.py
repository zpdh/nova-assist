"""Typed application configuration.

``WakeConfig`` is read from an optional TOML file (default: ``config.toml`` at
the repo root) and can be overridden by environment variables.

``LlmConfig`` is sourced from environment variables (``NOVA_*``). A local
``.env`` next to the TOML file is loaded automatically; real environment
variables take precedence over it.

Secrets must never live in the TOML file; they come from the environment.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from nova.brain.config import BrainConfig
from nova.store.config import StoreConfig
from nova.stt.config import SttConfig

ENV_PREFIX = "NOVA_"

# Repo root = two levels up from this file (src/nova/config.py -> repo root).
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"

DEFAULT_ENV_FILENAME = ".env"


DEFAULT_LLM_BASE_URL = "http://localhost:20128/v1"
DEFAULT_SEARCH_PROVIDER = "tavily"


@dataclass(frozen=True)
class LlmConfig:
    """LLM settings for an OpenAI-compatible endpoint.

    ``base_url`` and ``search_provider`` have defaults; ``api_key`` and
    ``model`` come from the environment and are required.
    """

    api_key: str
    model: str
    base_url: str = DEFAULT_LLM_BASE_URL
    search_provider: str = DEFAULT_SEARCH_PROVIDER


@dataclass(frozen=True)
class WakeConfig:
    """Wake-word detection settings."""

    phrase: str = "hey nova"


@dataclass(frozen=True)
class Config:
    """Top-level Nova configuration."""

    llm: LlmConfig
    wake: WakeConfig = field(default_factory=WakeConfig)
    stt: SttConfig = field(default_factory=SttConfig)
    brain: BrainConfig = field(default_factory=BrainConfig)
    store: StoreConfig = field(default_factory=StoreConfig)

    @classmethod
    def load(
        cls,
        path: Path | None = None,
        env_file: Path | Literal["auto"] | None = "auto",
    ) -> Config:
        """Build a config from the TOML file and the environment.

        Args:
            path: TOML file to read. Defaults to ``config.toml`` at the repo
                root. Missing files are ignored.
            env_file: ``.env`` file to load before reading the environment.
                ``"auto"`` (default) uses a ``.env`` next to the TOML file;
                ``None`` skips loading; a path uses that file. Existing
                environment variables are not overwritten.

        Raises:
            ValueError: if a required LLM environment variable is missing, or a
                configured value is invalid.
        """
        config_path = path if path is not None else DEFAULT_CONFIG_PATH
        config_dir = config_path.parent
        _load_dotenv(_resolve_env_file(env_file, config_dir))

        raw = _read_toml(config_path)
        wake_raw = raw.get("wake", {})
        stt_raw = raw.get("stt", {})
        brain_raw = raw.get("brain", {})
        store_raw = raw.get("store", {})

        wake = WakeConfig(
            phrase=_env("WAKE_PHRASE", _str_or(wake_raw, "phrase", WakeConfig.phrase)),
        )
        brain = BrainConfig(
            system_prompt=_env(
                "BRAIN_SYSTEM_PROMPT",
                _str_or(brain_raw, "system_prompt", BrainConfig.system_prompt),
            ),
        )
        llm = LlmConfig(
            api_key=_required_env("LLM_API_KEY"),
            model=_required_env("LLM_MODEL"),
            base_url=_env("LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
            search_provider=_env("LLM_SEARCH_PROVIDER", DEFAULT_SEARCH_PROVIDER),
        )
        stt = _build_stt_config(stt_raw, config_dir)
        store = StoreConfig(
            db_path=_path_env(
                "STORE_DB_PATH", _path_or(store_raw, "db_path", StoreConfig.db_path, config_dir)
            ),
        )
        return cls(llm=llm, wake=wake, stt=stt, brain=brain, store=store)


def _build_stt_config(section: dict, config_dir: Path) -> SttConfig:
    """Build an :class:`SttConfig` from TOML values + ``NOVA_STT_*`` env."""
    default = SttConfig()
    stt = SttConfig(
        backend=_env("STT_BACKEND", _str_or(section, "backend", default.backend)),
        model_path=_path_env(
            "STT_MODEL_PATH", _path_or(section, "model_path", default.model_path, config_dir)
        ),
        cli_path=_path_env(
            "STT_CLI_PATH", _path_or(section, "cli_path", default.cli_path, config_dir)
        ),
        server_path=_path_env(
            "STT_SERVER_PATH", _path_or(section, "server_path", default.server_path, config_dir)
        ),
        threads=int(_env("STT_THREADS", str(_int_or(section, "threads", default.threads)))),
        device=_env("STT_DEVICE", _str_or(section, "device", default.device)),
        server_port=int(
            _env("STT_SERVER_PORT", str(_int_or(section, "server_port", default.server_port)))
        ),
    )
    return stt.validated()


def _read_toml(path: Path) -> dict:
    """Read a TOML file, returning an empty dict if it does not exist."""
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _resolve_env_file(
    env_file: Path | Literal["auto"] | None,
    config_dir: Path,
) -> Path | None:
    """Turn the ``env_file`` argument into a path, or ``None`` to skip."""
    if env_file is None:
        return None
    if env_file == "auto":
        return config_dir / DEFAULT_ENV_FILENAME
    return env_file


def _load_dotenv(path: Path | None) -> None:
    """Load ``KEY=VALUE`` lines from ``path`` into the environment.

    Existing environment variables are kept. Blank lines and comments are
    ignored. A missing file is a no-op.
    """
    if path is None or not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _str_or(section: dict, key: str, default: str) -> str:
    """Read ``section[key]`` as a str, falling back to ``default``."""
    value = section.get(key, default)
    return str(value) if value is not None else default


def _path_or(section: dict, key: str, default: Path, base_dir: Path) -> Path:
    """Read ``section[key]`` as a path, falling back to ``default``.

    Relative paths are resolved against ``base_dir`` (the config file's
    directory) so behavior does not depend on the current working directory.
    """
    value = section.get(key)
    if value in (None, ""):
        return default
    path = Path(str(value))
    if not path.is_absolute():
        path = base_dir / path
    return path


def _int_or(section: dict, key: str, default: int) -> int:
    """Read ``section[key]`` as an int, falling back to ``default``."""
    value = section.get(key, default)
    return int(value)


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


def _path_env(suffix: str, default: Path) -> Path:
    """Return ``NOVA_<suffix>`` as a path, else ``default``."""
    value = _optional_env(suffix)
    return Path(value) if value is not None else default


__all__ = [
    "Config",
    "LlmConfig",
    "WakeConfig",
    "SttConfig",
    "BrainConfig",
    "StoreConfig",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_LLM_BASE_URL",
    "DEFAULT_SEARCH_PROVIDER",
    "ENV_PREFIX",
]
