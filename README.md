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
.venv/bin/pytest                     # unit tests (no hardware needed)
.venv/bin/pytest -m integration      # opt-in: real whisper.cpp + model
.venv/bin/ruff check .               # lint
.venv/bin/ruff format .              # format
```

### Test container (optional)

The hardware-free suite also runs in a clean Podman image:

```bash
podman build -f containers/test.Containerfile -t nova-test .
podman run --rm nova-test
```

## Configuration

- `config.toml` — non-secret defaults (currently the wake phrase).
- `.env` — secrets and deployment-specific settings, gitignored. Copy from
  `.env.example`.

The wake phrase is read from `config.toml` and can be overridden by
`NOVA_WAKE_PHRASE`. The `[stt]` section (`config.toml` / `NOVA_STT_*`) selects
the speech-to-text backend: `server` (resident model, lower latency) or `cli`.
LLM settings (`NOVA_LLM_*`) are read from the environment only and have no
defaults.

## Speech-to-text

The `nova.stt` package exposes a `Transcriber` protocol and a
`build_transcriber` factory. Backends:

- **server** (default): a resident `whisper-server`, model kept in VRAM,
  OpenAI-compatible `/inference`.
- **cli**: one `whisper-cli` invocation per file (simpler, reloads the model).

Both return a `Transcript` with text and optional word-level timings.

## Layout

```
src/nova/       application package
tests/          pytest suite
scripts/        build helpers (whisper.cpp Vulkan)
containers/     optional Podman build + test images
docs/           design notes and proofs
```
