# 01: Install local tooling

**What to build:** The machine can run the project. `uv` manages a modern Python (system Python is 3.9.5). Docker Desktop runs containers, with WSL2 enabled, which Windows Home needs. Claude Code is logged in with the Pro subscription, so that headless calls work without an API key.

**Blocked by:** None (can start immediately)

**Status:** ready-for-human

- [ ] `uv --version` works in a new terminal
- [ ] `docker run --rm hello-world` succeeds
- [ ] `claude -p "Reply with OK" --model claude-haiku-5-5` returns OK with no `ANTHROPIC_API_KEY` set
- [ ] Ticket file updated with the installed versions
