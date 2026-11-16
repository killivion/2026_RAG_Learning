# finbench-rag

Retrieval-augmented question answering over SEC filings, evaluated on FinanceBench with held-out results, confidence intervals and uncertainty estimates. Work in progress: see `.scratch/finbench-rag/spec.md` for scope and `.scratch/finbench-rag/issues/` for tickets.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/) and git. Docker (for pgvector) and a logged-in Claude Code CLI are needed for later milestones.

```bash
uv sync                      # creates .venv with Python 3.12 and all dependencies
uv run pre-commit install    # runs format, lint, types and tests before each commit
uv run pytest                # test suite; needs no network, Docker or LLM
uv run finbench run --config configs/smoke.yaml   # writes a run directory under runs/
uv run finbench download     # FinanceBench questions, annotations and 84 filings (about 165 MB)
uv run finbench data-summary # counts of questions, companies, filings and evidence pages
uv run finbench split        # only needed if splits/financebench.json is missing
uv run finbench llm-ping     # one real Claude call through Claude Code; the second run is cached
uv run pytest -m live        # opt-in test that makes one real LLM call
```

## Evaluation protocol

The 150 questions are split once into dev (51 questions, 10 companies) and test (99 questions, 22 companies). The split is grouped by company, so no company's filings are both tuned on and tested on, and each question type has the same share on both sides (`docs/adr/0001`). It is committed as `splits/financebench.json` and frozen: `finbench split` refuses to overwrite it. That file is the source of truth; the seed in it only records how it was made. `--force` exists, but using it after any dev result has been seen is a protocol violation, because the test questions would no longer be held out.

## LLM calls

Every LLM call goes through headless Claude Code on a Claude subscription, behind a swappable backend (`src/finbench/llm.py`, `docs/adr/0005`). Calls are cached on disk under `cache/llm/<backend>/`, keyed by model, prompts, schema and prompt version, so a rerun costs no usage and an interrupted run resumes. Reported cost is notional: list-price cost as the CLI reports it, not money spent.

## Data

FinanceBench (Islam et al., 2023, patronus-ai/financebench) is used for non-commercial research only. `finbench download` fetches the 150 questions, the document metadata, the 16 human-annotated completion files and the 84 filings into the git-ignored `data/` and `pdfs/` folders. They are never committed to this repository.

Every file is checked against `src/finbench/financebench_manifest.json`, which pins one upstream commit and holds each file's git blob hash. A rerun skips files that match and stops on any mismatch.
