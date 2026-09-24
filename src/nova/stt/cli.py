"""whisper.cpp CLI transcriber.

Runs ``whisper-cli`` once per file and parses its JSON output. Simpler than the
server backend (no background process) but reloads the model every call.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from nova.stt.config import SttConfig
from nova.stt.errors import SttError, SttUnavailable
from nova.stt.parsing import parse_cli_document
from nova.stt.types import Transcript

log = logging.getLogger(__name__)

# whisper-cli writes one file per requested format. ``-oj`` selects JSON and the
# produced file is named ``<output-prefix>.json`` (``-of`` is a path *prefix*,
# without an extension). Keep the flag and extension paired here.
_OUTPUT_FLAG = "-oj"
_OUTPUT_EXT = ".json"


class WhisperCliTranscriber:
    """Transcribes audio by invoking the ``whisper-cli`` binary."""

    def __init__(self, config: SttConfig) -> None:
        self._config = config.validated()
        self._binary = Path(config.cli_path)
        self._model = Path(config.model_path)

    def transcribe(self, wav_path: Path) -> Transcript:
        """Transcribe ``wav_path`` and return the parsed result."""
        self._check_available()
        wav_path = Path(wav_path)
        if not wav_path.is_file():
            raise SttUnavailable(f"audio file not found: {wav_path}")

        with tempfile.TemporaryDirectory(prefix="nova-stt-") as tmp:
            out_prefix = Path(tmp) / "out"
            cmd = self._build_command(wav_path, out_prefix)
            log.debug("running: %s", " ".join(cmd))
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError as exc:  # binary vanished / not executable
                raise SttUnavailable(f"failed to run whisper-cli: {exc}") from exc

            if result.returncode != 0:
                raise SttError(
                    f"whisper-cli exited with {result.returncode}: {result.stderr.strip()}"
                )

            json_path = out_prefix.with_suffix(_OUTPUT_EXT)
            if not json_path.is_file():
                raise SttError("whisper-cli did not produce JSON output")
            document = json.loads(json_path.read_text(encoding="utf-8"))

        return parse_cli_document(document)

    def close(self) -> None:
        """No-op: the cli backend holds no persistent resources."""

    def _build_command(self, wav_path: Path, out_prefix: Path) -> list[str]:
        cmd = [
            str(self._binary),
            "-m",
            str(self._model),
            "-f",
            str(wav_path),
            _OUTPUT_FLAG,  # JSON output -> <prefix>.json
            "-of",
            str(out_prefix),
            "-np",  # no extra prints
            "-t",
            str(self._config.threads),
        ]
        if self._config.device == "cpu":
            cmd.append("-ng")

        return cmd

    def _check_available(self) -> None:
        if not self._binary.is_file():
            raise SttUnavailable(f"whisper-cli binary not found: {self._binary}")
        if not self._model.is_file():
            raise SttUnavailable(f"model file not found: {self._model}")
