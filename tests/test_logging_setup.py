"""Tests for :mod:`nova.logging_setup`."""

from __future__ import annotations

import logging
from datetime import date

import pytest

from nova import logging_setup


@pytest.fixture(autouse=True)
def _reset_logging():
    """Isolate each test: reset module state and detach handlers."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    logging_setup._configured = False
    logging_setup._log_path = None
    yield
    for handler in list(root.handlers):
        if handler not in original_handlers:
            handler.close()
            root.removeHandler(handler)
    root.setLevel(original_level)


def test_creates_dated_log_file(tmp_path):
    path = logging_setup.setup_logging("INFO", log_dir=tmp_path)

    assert path is not None
    assert path.name == f"nova-{date.today().isoformat()}.log"
    assert path.parent == tmp_path


def test_second_run_same_day_gets_suffix(tmp_path):
    first = logging_setup.setup_logging("INFO", log_dir=tmp_path)

    # Simulate a fresh process.
    logging_setup._configured = False
    logging_setup._log_path = None
    second = logging_setup.setup_logging("INFO", log_dir=tmp_path)

    assert first is not None and second is not None
    assert second.name == f"nova-{date.today().isoformat()}-2.log"


def test_writes_to_file(tmp_path):
    path = logging_setup.setup_logging("INFO", log_dir=tmp_path)
    logging.getLogger("nova.test").info("hello file")

    assert path is not None
    assert "hello file" in path.read_text()


def test_repeated_calls_do_not_duplicate_handlers(tmp_path):
    logging_setup.setup_logging("INFO", log_dir=tmp_path)
    count_after_first = len(logging.getLogger().handlers)

    logging_setup.setup_logging("DEBUG", log_dir=tmp_path)

    assert len(logging.getLogger().handlers) == count_after_first
    assert logging.getLogger().level == logging.DEBUG


def test_current_log_path_reflects_setup(tmp_path):
    path = logging_setup.setup_logging("INFO", log_dir=tmp_path)

    assert logging_setup.current_log_path() == path


def test_falls_back_when_dir_unwritable(tmp_path):
    # A file where a directory is expected makes mkdir fail.
    blocker = tmp_path / "logs"
    blocker.write_text("not a dir")

    path = logging_setup.setup_logging("INFO", log_dir=blocker)

    assert path is None
    # Console handler must still be attached.
    assert any(isinstance(h, logging.StreamHandler) for h in logging.getLogger().handlers)
