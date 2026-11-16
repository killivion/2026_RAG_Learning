# 01: Install local tooling

**What to build:** The machine can run the project. `uv` manages a modern Python (system Python is 3.9.5). Docker Desktop runs containers, with WSL2 enabled, which Windows Home needs. Claude Code is logged in with the Pro subscription, so that headless calls work without an API key.

**Blocked by:** None (can start immediately)

**Status:** ready-for-human

- [x] `uv --version` works in a new terminal
- [ ] `docker run --rm hello-world` succeeds
- [x] `claude -p "Reply with OK" --model claude-haiku-5-5` returns OK with no `ANTHROPIC_API_KEY` set
- [ ] Ticket file updated with the installed versions

## Comments

- 2026-11-17 (Claude): checked from the agent session.
  - `uv` 0.13.8 works.
  - Docker 29.9.3 and Compose v5.7.0 are installed, but the engine was not running: `docker info` could not reach it, also after starting Docker Desktop and waiting. `docker run --rm hello-world` is therefore still open. Docker Desktop may be waiting for its first-run steps (licence, WSL2).
  - Claude Code 2.1.317 answers headless calls from inside the agent session (ticket 03). The check in a plain terminal without `ANTHROPIC_API_KEY` is still yours to run.
- 2026-11-17: the user ran `claude -p "Reply with OK" --model claude-haiku-5-5` in the app's terminal panel with `ANTHROPIC_API_KEY` empty; it returned `OK`.
