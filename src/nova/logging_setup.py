"""Logging configuration for Nova.

A single :func:`setup_logging` entry point so every entry point (CLI, TUI,
background service) logs consistently. Logs go to stderr *and* a dated file
under the repo's ``logs/`` directory. Kept dependency-free and idempotent.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DEFAULT_LEVEL = "INFO"

# Repo root: src/nova/logging_setup.py -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = _REPO_ROOT / "logs"

_configured = False
_log_path: Path | None = None


def setup_logging(level: str | int | None = None, log_dir: Path | None = None) -> Path | None:
    """Configure the root logger once, for both console and a dated file.

    The level resolves from ``level``, else ``NOVA_LOG_LEVEL``, else ``INFO``.
    The file lives in ``log_dir`` (default ``logs/`` at the repo root) named
    ``nova-YYYY-MM-DD.log``; if that exists, ``-2``, ``-3``, ... are tried.

    Returns the path of the log file, or ``None`` if it could not be opened
    (logging then continues on the console only). Repeated calls adjust the
    level but do not add handlers again.
    """
    global _configured, _log_path

    root = logging.getLogger()
    root.setLevel(_resolve_level(level))

    if _configured:
        return _log_path

    formatter = logging.Formatter(DEFAULT_FORMAT)
    root.addHandler(_stream_handler(formatter))

    _log_path, file_handler = _open_log_file(log_dir if log_dir is not None else DEFAULT_LOG_DIR)
    if file_handler is not None:
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    _configured = True
    return _log_path


def _stream_handler(formatter: logging.Formatter) -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    return handler


def _open_log_file(log_dir: Path) -> tuple[Path | None, logging.Handler | None]:
    """Create a uniquely named dated log file and a handler for it.

    Returns ``(path, handler)`` or ``(None, None)`` on failure, so a logging
    problem can never crash the app.
    """
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        path = _unique_log_path(log_dir)
        handler: logging.Handler | None = logging.FileHandler(path, encoding="utf-8")
    except OSError as exc:
        logging.getLogger(__name__).warning("cannot open log file: %s", exc)
        return None, None
    return path, handler


def _unique_log_path(log_dir: Path) -> Path:
    """Return a dated log path, appending ``-N`` until a free name is found.

    Uses an exclusive create so two concurrent processes cannot pick the same
    name (avoids a race of its own).
    """
    stamp = date.today().isoformat()
    suffix = 1
    while True:
        name = f"nova-{stamp}.log" if suffix == 1 else f"nova-{stamp}-{suffix}.log"
        candidate = log_dir / name
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            suffix += 1
            continue
        os.close(fd)
        return candidate


def current_log_path() -> Path | None:
    """Return the path of the log file chosen on first setup, if any."""
    return _log_path


def _resolve_level(level: str | int | None) -> int:
    """Coerce a level name/number/env var into a logging level int."""
    if level is None:
        level = os.environ.get("NOVA_LOG_LEVEL", DEFAULT_LEVEL)
    if isinstance(level, int):
        return level

    return logging.getLevelNamesMapping()[level.upper()]


__all__ = [
    "setup_logging",
    "current_log_path",
    "DEFAULT_FORMAT",
    "DEFAULT_LEVEL",
    "DEFAULT_LOG_DIR",
]
