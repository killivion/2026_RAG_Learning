# 04: Dataset download

**What to build:** One command fetches everything FinanceBench provides for this project into git-ignored folders, and checks every file against committed checksums:
- the 150 questions;
- the document metadata;
- the 16 human-annotated completion files;
- the 84 filings our questions use.

Questions load as typed objects: id, company, filing, question type, question, gold answer, evidence pages (zero-indexed, with evidence text). A summary command prints the counts.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] `finbench download` is idempotent: a rerun skips files whose checksum matches and fails loudly on a mismatch
- [ ] `finbench data-summary` prints 150 questions, 32 companies, 84 filings, question types 50/50/50, and evidence-page counts of 115/31/4
- [ ] No data or PDFs are tracked by git (`git status` stays clean after download)
- [ ] Loader tests run on a small committed fixture, not the real data
