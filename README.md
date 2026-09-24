# Nova

A local, always-listening voice assistant for the desktop (Fedora / KDE).

Say **"Hey Nova"** and it listens, transcribes locally, asks a language model
(optionally with web search), and answers — by voice and in a terminal UI.

## Status

Incremental build. Current progress:

- **I0/I1 — STT GPU proof:** whisper.cpp (Vulkan) builds and runs on the AMD GPU.
  See [`docs/stt-gpu-proof.md`](docs/stt-gpu-proof.md).
- **I2 — Project skeleton:** package layout, typed config, logging, tests.

## Requirements

- Python 3.14
- For the speech engine (see I0/I1):
  - `sudo dnf install cmake gcc-c++ glslc vulkan-loader-devel spirv-headers-devel glslang`

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Development

```bash
.venv/bin/pytest          # run tests
.venv/bin/ruff check .    # lint
.venv/bin/ruff format .   # format
```

## Configuration

- `config.toml` — non-secret defaults (wake phrase, gateway URL, models).
- `.env` — secrets and local overrides (gitignored). Copy from `.env.example`.

Precedence: defaults → `config.toml` → environment (`NOVA_*`).

## Layout

```
src/nova/       application package
tests/          pytest suite
scripts/        build helpers (whisper.cpp Vulkan)
containers/     optional Podman build for whisper.cpp
docs/           design notes and proofs
```
