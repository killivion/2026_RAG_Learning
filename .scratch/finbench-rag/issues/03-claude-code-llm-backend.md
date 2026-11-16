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

**Status:** ready-for-agent

- [ ] A command (e.g. `finbench llm-ping`) returns a schema-valid JSON object from `claude-haiku-5-5`, with tokens and notional cost
- [ ] The second identical call is served from the cache: no subprocess runs, and the latency is recorded as cached
- [ ] Tests with the fake backend cover a cache hit, a cache miss after a prompt-version change, and a usage-limit stop
- [ ] An opt-in live test (skipped by default and in CI) makes one real call
- [ ] Terms-of-use outcome recorded in ADR-0005
