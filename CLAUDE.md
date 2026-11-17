# finbench-rag

`.scratch/finbench-rag/spec.md` is the source of truth for scope and milestones. Its tickets are in `.scratch/finbench-rag/issues/`. Work the lowest-numbered unblocked `ready-for-agent` ticket.

The workflow, doc layout and `NOTES.md` template are in `~/.claude/CLAUDE.md`. This file adds what only this project needs.

## Project rules

- `README.md` is the technical report (M5). There is no presentation notebook.
- Every choice is made on the dev split; the test split is only for reporting (`docs/adr/0001`).
- Never commit FinanceBench data or PDFs (private repo, non-commercial data).
- Commit and push to `origin` at the end of each completed ticket or milestone.
- Start a job longer than a minute with `uv run --no-sync python -m finbench.cli <command>`. The plain `finbench` launcher is locked while it runs, which blocks `uv add`, `uv sync` and the pre-commit hook.
- Reported numbers come from `results/`: after new runs, `finbench summarize` rewrites `results/retrieval_runs.csv`, and README, tickets and learning notes cite that file.
- Test seams are fixed in the spec's "Testing Decisions".

## Context budget

Keep a session well under 300k tokens.

- **One ticket per session.** A ticket ends with commit, push and a short ticket comment: decisions, gotchas and pointers, with numbers left in `results/`. That comment is the handoff. Then offer the next ticket as a new session instead of starting it here.
- **Delegate output-heavy work** (data probes, real-data checks, comparisons across configs) to a subagent that returns only the numbers.
- **Edit in place.** Change existing files with Edit; use Write only to create a file. Keep each shell call to one command or one script file.
- **Format once:** run `ruff format` on the changed files right before the commit.
- **Read narrowly.** One file per read, in line ranges where possible; trim command output to the lines needed (`| tail`, `-q`, `sed -n`, or a script that prints only the fields).

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five canonical labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root, both created lazily. See `docs/agents/domain.md`.
