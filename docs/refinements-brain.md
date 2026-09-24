# Brain refinements (pre-I4)

Three small changes to the brain, made before working on the store (I4). They
are independent of I4 but prepare the ground for the session service.

## 1. Response decoding (SSE-tagged bodies)

**Why.** The gateway replies with `Content-Type: text/event-stream` even for
non-streamed requests, and appends `data: [DONE]` **directly after** the JSON
object, with no separator. The JSON is not framed by `data:`. Parsing the whole
body as JSON fails with `Extra data`.

**Change.** Renamed `_parse_json` to `parse_json_response` (now shared decode
policy) and documented the wire shape. The search client uses the same helper,
so the None-check and error message live in one place.

- `src/nova/brain/client.py` — `parse_json_response` (docstring describes the
  trailing marker); `decode_first_json` unchanged.
- `src/nova/brain/search.py` — calls `parse_json_response(response, "search endpoint")`.

**Out of scope.** Real multi-event SSE streaming (`stream: true`) is not
supported; first-object decoding would return only the first delta.

## 2. System prompt moved to config

**Why.** The system prompt is content, not logic. It was a module constant
(`SYSTEM_PROMPT`) exported from the brain, with no external consumer. The brain
also always prepended it, which mixes "what to send" with "policy".

**Change.** The prompt is now configuration and the **caller** supplies it.

- New `BrainConfig` (`src/nova/brain/config.py`) with `system_prompt`.
- `config.toml` gains `[brain] system_prompt = "..."`; override with
  `NOVA_BRAIN_SYSTEM_PROMPT`.
- `Brain.chat()` no longer prepends a system message; it sends the messages it
  is given. `SYSTEM_PROMPT` is removed.
- The CLI (`python -m nova.brain`) now composes
  `[system(prompt), user(question)]` itself.

**Rule for callers.** Anyone calling `brain.chat(...)` must include the system
message if they want one. The brain trusts the caller.

## 3. `ChatResult` carries the turn transcript

**Why.** `ChatResult.tool_calls` only reflected the **final** response's tool
calls, which is usually empty on success. The assistant tool-call turn and the
tool-result messages lived only in a local list inside `chat()` and were
discarded. Persisting history faithfully (I4) needs those messages.

**Change.** `ChatResult` now exposes `turns` — the messages generated this turn.

Before:

```python
@dataclass(frozen=True)
class ChatResult:
    text: str
    model: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    usage: dict[str, Any] = field(default_factory=dict)
```

After:

```python
@dataclass(frozen=True)
class ChatResult:
    text: str
    model: str = ""
    turns: tuple[Message, ...] = ()
    usage: dict[str, Any] = field(default_factory=dict)
```

- The raw model response is now a separate internal type, `Completion`
  (`text`, `model`, `tool_calls`, `usage`), returned by `ChatClient.complete`.
  The tool loop reads `tool_calls` from it.
- `Brain.chat` builds the public `ChatResult`, collecting `turns` as it goes:
  each assistant tool-call turn, the tool results, and the final assistant turn.
- On the round-limit exit, the last (unrun) assistant tool-call turn is still
  recorded, so history keeps the model's final request.

Example trace (`"search then answer"`):

```
turns = [assistant(tool_calls=[web_search]),   # requested the search
         tool(content="...results..."),        # search output
         assistant(content="the answer")]      # final answer
```

## Impact on I4

The session service will:

```
history = repo.load(session_id)
messages = [system(config.brain.system_prompt), *history, user(text)]
result = brain.chat(messages)
repo.append(session_id, user(text))
repo.append_all(session_id, result.turns)
return result.text
```

The brain stays stateless and testable; the service owns composition and
persistence.

## Verification

- `pytest tests/brain tests/test_config.py` — all green.
- Live: `python -m nova.brain "..."` returns an answer; a search question yields
  `turns = [assistant, tool, assistant]` and `ChatResult` has no `tool_calls`.
