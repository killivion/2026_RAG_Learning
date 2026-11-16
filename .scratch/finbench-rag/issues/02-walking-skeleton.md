# 02: Walking skeleton

**What to build:** An empty but complete project that every later ticket plugs into:
- a uv project with src layout, ruff, mypy (strict), pytest and pre-commit;
- a Typer command line with a `run` command that loads a config file into the validated config model (see spec, Implementation Decisions → Config);
- a no-op run that writes a run directory with the config, config hash, git commit, split name and an empty metrics file;
- GitHub Actions CI running lint, types and tests on push.

**Blocked by:** 01

**Status:** done (CI result to be confirmed by the user on GitHub)

- [x] `uv run finbench run --config <smoke config>` writes a run directory with the four items above
- [x] An invalid config (unknown key or wrong type) fails with a readable error
- [x] `uv run pytest`, `uv run ruff check` and `uv run mypy` pass locally; pre-commit runs them
- [ ] CI is green on GitHub for the pushed commit
- [x] README has a minimal "Setup" section

## Comments

- 2026-11-16: Implemented. A reviewer pass found no blockers. Applied fixes: readable error for malformed YAML, microsecond run-directory names so back-to-back runs don't collide, a `Split` enum for `--split`, and CI triggered on push only. Kept: `_git_commit` falls back to "unknown" outside a git repo. CI could not be checked from here (no `gh` CLI).
