# finbench-rag

`PLAN.md` is the source of truth for scope and milestones.

## Overrides of the parent CLAUDE.md

These replace the parent folder's documentation rules for this project only:
- **No NOTES.md.** Its interview role moves to `learning/` (see `learning/README.md`): one note per concept plus `learning/00-pitch.md`. Draft a note at the end of each milestone; the user rewrites it.
- **No presentation notebook.** `README.md` is the technical report (M5).
- **Decisions** go into `docs/adr/` (only hard-to-reverse ones) and **vocabulary** into `GLOSSARY.md`. Small choices live in config.
- **"Every change updates docs"** here means: README.md when the report changes, GLOSSARY.md for new terms, an ADR for a new hard-to-reverse decision.
- **"Full review"** checks code, README, PLAN, GLOSSARY, ADRs and `learning/` for consistency.

## Project rules

- Every choice is made on the dev split; the test split is only for reporting (`docs/adr/0001`).
- Never commit FinanceBench data or PDFs (private repo, non-commercial data).
- Commit and push to `origin` at the end of each completed ticket or milestone.

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five canonical labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root, both created lazily. See `docs/agents/domain.md`.
