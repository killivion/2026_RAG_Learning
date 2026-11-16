# 04: Dataset download

**What to build:** One command fetches everything FinanceBench provides for this project into git-ignored folders, and checks every file against committed checksums:
- the 150 questions;
- the document metadata;
- the 16 human-annotated completion files;
- the 84 filings our questions use.

Questions load as typed objects: id, company, filing, question type, question, gold answer, evidence pages (zero-indexed, with evidence text). A summary command prints the counts.

**Blocked by:** 02

**Status:** done

- [x] `finbench download` is idempotent: a rerun skips files whose checksum matches and fails loudly on a mismatch
- [x] `finbench data-summary` prints 150 questions, 32 companies, 84 filings, question types 50/50/50, and evidence-page counts of 115/31/4
- [x] No data or PDFs are tracked by git (`git status` stays clean after download)
- [x] Loader tests run on a small committed fixture, not the real data

## Comments

- 2026-11-16: Implemented in `src/finbench/dataset.py`, with `finbench download`, `finbench data-summary` and `tests/test_dataset.py`. The real download fetched 102 files (about 165 MB); a rerun skipped all 102; `data-summary` printed the expected counts; `git status` shows no data.
- **Source and checksums.** Files come from `patronus-ai/financebench` on GitHub, pinned to commit `cc39aeb` (2024-12-03). The committed manifest `src/finbench/financebench_manifest.json` lists the 102 files with their git blob hashes, taken from GitHub's tree for that commit. So the checksums come from git itself, not from a first download that we would have to trust.
- **Layout.** Upstream `data/` and `pdfs/` keep their names; upstream `results/` (the 16 human-annotated completion files) goes to `data/results/`.
- **`.gitignore` fix.** `data/` and `pdfs/` are now anchored to the repo root (`/data/`, `/pdfs/`), because the old pattern also ignored the test fixture folder.
- **Evidence pages.** `evidence_pages` keeps one entry per FinanceBench evidence item, which gives the 115/31/4 counts. Two of the four questions with three items have two of them on the same page, so by distinct page the counts are 115/33/2. Page-level metrics (ticket 08) must use the set of distinct pages.
- **Not built here.** The document metadata and the completion files are downloaded and checked, but no loader exists for them yet; nothing needs one before M2 (judge validation).
- The fixture in `tests/fixtures/financebench/` is synthetic and holds no FinanceBench text.
