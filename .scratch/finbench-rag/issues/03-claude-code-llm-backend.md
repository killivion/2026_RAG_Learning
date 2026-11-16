# 03: Claude Code LLM backend with cache

**What to build:** Experiment code can ask Claude for structured output on the Pro subscription (ADR-0005):
- The LLM backend interface takes model, system prompt, user prompt and JSON schema. It returns parsed output, token usage, notional cost and latency.
- The headless Claude Code implementation makes one turn, with no tools, our own system prompt, schema-validated JSON and no session persistence.
- A disk cache wraps any backend. Its key covers model, prompts, schema and prompt version.
- A usage-limit failure raises one specific exception, and a rerun resumes from the cache.
- A scripted fake backend serves tests.
- The exact CLI flags and the reported usage and cost fields are verified on the real CLI. Write what you found into this ticket.
- Check Anthropic's consumer terms for automated use of the subscription and record the outcome in ADR-0005. If such use is not allowed, stop and flag it to the user.

**Blocked by:** 02

**Status:** done

- [x] A command (e.g. `finbench llm-ping`) returns a schema-valid JSON object from `claude-haiku-5-5`, with tokens and notional cost
- [x] The second identical call is served from the cache: no subprocess runs, and the latency is recorded as cached
- [x] Tests with the fake backend cover a cache hit, a cache miss after a prompt-version change, and a usage-limit stop
- [x] An opt-in live test (skipped by default and in CI) makes one real call
- [x] Terms-of-use outcome recorded in ADR-0005

## Comments

- 2026-11-16: Implemented in `src/finbench/llm.py`, with `finbench llm-ping` and `tests/test_llm.py`.

### What the real CLI does (Claude Code 2.1.317)

Command, with the user prompt on stdin:

```
claude --print --model <id> --system-prompt <text> --json-schema <json> --output-format json
       --tools "" --no-session-persistence --strict-mcp-config --disable-slash-commands
       --setting-sources ""
```

- `--output-format json` prints one result object as the last stdout line. A diagnostic line can come before it.
- Fields used: `structured_output` (the schema-valid object), `usage.input_tokens`, `usage.cache_creation_input_tokens`, `usage.cache_read_input_tokens`, `usage.output_tokens`, `total_cost_usd`, `is_error`, `subtype`, `api_error_status`, `result` (the error text on failure).
- `total_cost_usd` is at list prices (`modelUsage.<model>.costBasis` is `"list"`), so it is our notional cost. The docs call it a client-side estimate.
- `input_tokens` in our response is the sum of the three input fields. Even a one-line prompt costs about 1,500–2,900 input tokens, because the CLI adds its own framing and the structured-output tool. Most of it is a prompt-cache write.
- `num_turns` is 2 for a structured-output call (the model calls the output tool once). This is still one user turn.
- A failure (tested with an unknown model id) exits with code 1 and still prints the result object, with `is_error: true`.
- `--setting-sources ""` and a neutral working directory keep local hooks, plugins and CLAUDE.md out of the calls. Login still works.

### Not verified

- **The usage-limit failure was never seen.** Detection is a guess: `is_error` with `api_error_status` 429, or the words "usage limit", "session limit", "weekly limit" or "rate limit" in `result`. When the first real limit is hit, check the output and fix `_USAGE_LIMIT_MARKERS` if needed. Until then a limit may surface as a plain `LLMBackendError`; the run still stops and the cache still resumes.
- The verification calls ran from inside a Claude Code desktop session, which passes its own login to child processes. Ticket 01's check (`claude -p` in a plain terminal) confirms the same for the subscription login.

### Choices

- A cached response keeps the latency of the original call and sets `cached: true`, so latency statistics stay meaningful on a rerun.
- Failed calls are not cached.
- Plain `uv run pytest` now deselects `live` tests; run them with `uv run pytest -m live`.
