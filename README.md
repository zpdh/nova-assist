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

- `config.toml` — non-secret defaults (wake phrase, prompt, paths).
- `.env` — secrets and deployment-specific settings, gitignored. Copy from
  `.env.example`. It is **loaded automatically** (next to `config.toml`) at
  `Config.load`; real environment variables take precedence over it.

The wake phrase is read from `config.toml` and can be overridden by
`NOVA_WAKE_PHRASE`. The `[stt]` section (`config.toml` / `NOVA_STT_*`) selects
the speech-to-text backend: `server` (resident model, lower latency) or `cli`.
LLM settings come from the environment:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `NOVA_LLM_BASE_URL` | no | `http://localhost:20128/v1` | OpenAI-compatible endpoint |
| `NOVA_LLM_API_KEY` | yes | — | bearer token |
| `NOVA_LLM_MODEL` | yes | — | model id to use |
| `NOVA_LLM_SEARCH_PROVIDER` | no | `tavily` | provider id for the search endpoint |

## Speech-to-text

The `nova.stt` package exposes a `Transcriber` protocol and a
`build_transcriber` factory, so callers never touch whisper.cpp directly.
Both backends come from the same whisper.cpp project; they differ in process
model, not in engine.

| Backend | Process model | Per-call latency | Use when |
|---|---|---|---|
| **server** (default) | one long-lived `whisper-server`, model resident in VRAM | encode + decode only (~120 ms tiny) | the assistant runs interactively / always-on — the normal case |
| **cli** | one `whisper-cli` run per file | includes model load (~80 ms tiny) | tests, batch, fallback, or a quick one-off |

Both return a `Transcript` with the text and optional word-level timings.
A future `stream` backend (whisper-stream) will serve continuous wake-word
spotting; the protocol is kept narrow so adding one is not a rewrite.

### Notes

- The server is started lazily on first use and stopped by `close()` (or via
  `with`). Selecting a port is subject to a probe/bind race, so startup is
  retried up to 3 times with a fresh port before failing.
- One HTTP client is reused for the server's lifetime.

## Brain

The `nova.brain` package answers a message with an OpenAI-compatible model and
can search the web. `build_brain` wires a chat client, a model router, and the
tool dispatchers from configuration; callers use `Brain` only.

- `Brain.ask(text)` — one question in, the answer text out.
- `Brain.chat(messages)` — a conversation, returning a `ChatResult`.

When the model asks for `web_search`, the brain calls the gateway's
`/search` endpoint, feeds the results back, and repeats up to
`MAX_TOOL_ROUNDS` (2) times. A `ModelRouter` (a Strategy) chooses the model;
the current implementation always returns the configured one.

### Demo

```bash
python -m nova.brain "what is the capital of France"
```

Requires `NOVA_LLM_API_KEY` and `NOVA_LLM_MODEL` in `.env`. Some models reject
tool calls (web search needs a tool-capable model).

The system prompt comes from config (`config.toml [brain]`,
`NOVA_BRAIN_SYSTEM_PROMPT`). The CLI composes `[system, user]`; `Brain.chat`
itself is stateless.

## Store

The `nova.store` package persists conversations in SQLite. A `Repository`
(a gateway that hides the database) stores sessions and messages; a
`Session` service composes it with the brain.

- `Repository` — `create_session`, `append`, `append_all`, `load`, `list_sessions`.
- `Session.ask(text)` — loads history, prepends the system prompt, asks the
  brain, and persists the user message plus the generated turns.
- Session ids are **uuid7** (time-ordered), so `list_sessions()` is chronological.
- The database lives at `data/nova.db` (gitignored); override with
  `NOVA_STORE_DB_PATH`.

### Demo — a persisted conversation

```bash
python -m nova.brain --session demo "My name is Antunes. Remember it."
python -m nova.brain --session demo "What is my name?"   # recalls it across runs
```

Without `--session`, the CLI stays one-shot (no persistence).

## Logging

Logs go to **stderr** and to a dated file under `logs/`:

```
logs/nova-2026-09-24.log      # first run that day
logs/nova-2026-09-24-2.log    # next run, same day
```

The level is taken from `NOVA_LOG_LEVEL` (default `INFO`). If the log file
cannot be opened, logging continues on the console only. `logs/` is gitignored.

## Layout

```
src/nova/       application package
tests/          pytest suite
scripts/        build helpers (whisper.cpp Vulkan)
containers/     optional Podman build + test images
docs/           design notes and proofs
logs/           runtime logs (gitignored)
```
