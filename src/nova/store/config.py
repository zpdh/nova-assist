"""Configuration for the store layer.

Values come from the ``[store]`` section of ``config.toml`` and can be
overridden by ``NOVA_STORE_*`` environment variables.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Repo root: src/nova/store/config.py -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class StoreConfig:
    """Settings for the SQLite store."""

    db_path: Path = _REPO_ROOT / "data" / "nova.db"


__all__ = ["StoreConfig"]
