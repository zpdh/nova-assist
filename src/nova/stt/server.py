"""whisper.cpp server transcriber.

Manages a long-lived ``whisper-server`` process so the model stays resident in
VRAM between calls (lower per-command latency than the cli backend), and posts
audio to its OpenAI-compatible ``/inference`` endpoint.

Process lifecycle: started lazily on first ``transcribe``, stopped by
``close``. Implements :class:`contextlib.AbstractContextManager` so it can be
used with ``with`` for guaranteed cleanup.
"""

from __future__ import annotations

import logging
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from types import TracebackType

import httpx

from nova.stt.config import SttConfig
from nova.stt.errors import SttError, SttTimeout, SttUnavailable
from nova.stt.parsing import parse_response
from nova.stt.types import Transcript

log = logging.getLogger(__name__)


class _StartupFailed(Exception):
    """Internal: a whisper-server startup attempt failed and may be retried."""


_STARTUP_TIMEOUT_S = 30.0
_REQUEST_TIMEOUT_S = 120.0

# Port collisions are rare: probing a port and then having whisper-server bind
# it is a TOCTOU race (the port is unowned between our probe and its bind).
# whisper-server has no socket-activation support, so we cannot hand it a
# reserved socket; instead we retry the whole startup with a fresh port.
_STARTUP_ATTEMPTS = 3


class WhisperServerTranscriber:
    """Transcribes audio via a resident ``whisper-server`` process."""

    def __init__(self, config: SttConfig) -> None:
        self._config = config.validated()
        self._binary = Path(config.server_path)
        self._model = Path(config.model_path)
        self._host = "127.0.0.1"
        self._port = config.server_port
        self._process: subprocess.Popen[bytes] | None = None
        self._log_path: Path | None = None
        self._log_file = None
        # One client reused across requests; closed by close(). A shared,
        # app-scoped client will be introduced with the app context in I5.
        self._client = httpx.Client(timeout=_REQUEST_TIMEOUT_S)

    # -- public API -------------------------------------------------------

    def transcribe(self, wav_path: Path) -> Transcript:
        """Ensure the server is running, then transcribe ``wav_path``."""
        wav_path = Path(wav_path)
        if not wav_path.is_file():
            raise SttUnavailable(f"audio file not found: {wav_path}")
        self._ensure_started()

        url = f"http://{self._host}:{self._port}/inference"
        try:
            with wav_path.open("rb") as fh:
                response = self._client.post(
                    url,
                    files={"file": (wav_path.name, fh, "audio/wav")},
                    data={"response_format": "verbose_json"},
                )
        except httpx.TimeoutException as exc:
            raise SttTimeout(f"transcription request timed out: {url}") from exc
        except httpx.HTTPError as exc:
            raise SttError(f"request to whisper-server failed: {exc}") from exc

        if response.status_code != 200:
            raise SttError(
                f"whisper-server returned {response.status_code}: {response.text.strip()}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise SttError("whisper-server returned invalid JSON") from exc
        return parse_response(payload)

    def close(self) -> None:
        """Terminate the server process and release resources (idempotent)."""
        self._stop_process()
        if not self._client.is_closed:
            self._client.close()

    def _stop_process(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            self._close_log()
            return
        log.debug("stopping whisper-server (pid=%s)", process.pid)
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            log.warning("whisper-server did not stop; killing (pid=%s)", process.pid)
            process.kill()
            process.wait(timeout=5)
        self._close_log()

    def _close_log(self) -> None:
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None

    def __enter__(self) -> WhisperServerTranscriber:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- internals --------------------------------------------------------

    def _ensure_started(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self._check_available()

        last_error: Exception | None = None
        for attempt in range(1, _STARTUP_ATTEMPTS + 1):
            # Pick a fresh port each attempt to absorb a TOCTOU collision.
            self._port = _free_port(self._config.server_port, self._host)
            try:
                self._start_process()
                self._wait_until_ready()
                return
            except _StartupFailed as exc:
                last_error = exc
                log.debug(
                    "whisper-server startup attempt %d/%d failed: %s",
                    attempt,
                    _STARTUP_ATTEMPTS,
                    exc,
                )
                self._stop_process()

        raise SttUnavailable(
            f"whisper-server failed to start after {_STARTUP_ATTEMPTS} attempts: {last_error}"
        )

    def _start_process(self) -> None:
        cmd = [
            str(self._binary),
            "-m",
            str(self._model),
            "--host",
            self._host,
            "--port",
            str(self._port),
            "-t",
            str(self._config.threads),
        ]
        if self._config.device == "cpu":
            cmd.append("-ng")

        self._log_path = _server_log_path()
        log.debug("starting: %s (log: %s)", " ".join(cmd), self._log_path)
        try:
            self._log_file = self._log_path.open("wb")
            self._process = subprocess.Popen(
                cmd,
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
            )
        except OSError as exc:
            raise SttUnavailable(f"failed to start whisper-server: {exc}") from exc

    def _wait_until_ready(self) -> None:
        assert self._process is not None
        deadline = time.monotonic() + _STARTUP_TIMEOUT_S
        url = f"http://{self._host}:{self._port}/"
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise _StartupFailed(
                    f"whisper-server exited during startup (code {self._process.returncode}); "
                    f"see {self._log_path}"
                )
            try:
                self._client.get(url, timeout=1.0)
                return
            except httpx.HTTPError:
                time.sleep(0.1)
        raise _StartupFailed(f"whisper-server did not become ready within {_STARTUP_TIMEOUT_S}s")

    def _check_available(self) -> None:
        if not self._binary.is_file():
            raise SttUnavailable(f"whisper-server binary not found: {self._binary}")
        if not self._model.is_file():
            raise SttUnavailable(f"model file not found: {self._model}")


def _free_port(preferred: int, host: str) -> int:
    """Return ``preferred`` if bindable, else an ephemeral free port."""
    for candidate in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
            except OSError:
                continue
            return sock.getsockname()[1]

    raise SttUnavailable("no free port available for whisper-server")


def _server_log_path() -> Path:
    return Path(tempfile.gettempdir()) / "nova-whisper-server.log"
