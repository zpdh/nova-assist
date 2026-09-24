"""Configuration for the speech-to-text layer.

Values come from the ``[stt]`` section of ``config.toml`` and can be overridden
by ``NOVA_STT_*`` environment variables.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BACKEND_SERVER = "server"
BACKEND_CLI = "cli"
_BACKENDS = frozenset({BACKEND_SERVER, BACKEND_CLI})

DEVICE_AUTO = "auto"

# Repo root: src/nova/stt/config.py -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_BIN_DIR = _REPO_ROOT / "third_party" / "whisper.cpp" / "build" / "bin"


@dataclass(frozen=True)
class SttConfig:
    """Settings for the speech-to-text backend."""

    backend: str = BACKEND_SERVER
    model_path: Path = _REPO_ROOT / "models" / "ggml-tiny.en.bin"
    cli_path: Path = _DEFAULT_BIN_DIR / "whisper-cli"
    server_path: Path = _DEFAULT_BIN_DIR / "whisper-server"
    threads: int = 4
    device: str = DEVICE_AUTO
    server_port: int = 18090

    def validated(self) -> SttConfig:
        """Return self after checking enumerations.

        Raises:
            ValueError: if ``backend`` or ``device`` is not a known value.
        """
        if self.backend not in _BACKENDS:
            raise ValueError(
                f"unknown stt backend {self.backend!r}; expected one of {sorted(_BACKENDS)}"
            )
        return self


__all__ = ["SttConfig", "BACKEND_SERVER", "BACKEND_CLI", "DEVICE_AUTO"]
