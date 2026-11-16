# finbench-rag

Retrieval-augmented question answering over SEC filings, evaluated on FinanceBench with held-out results, confidence intervals and uncertainty estimates. Work in progress: see `.scratch/finbench-rag/spec.md` for scope and `.scratch/finbench-rag/issues/` for tickets.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/) and git. Docker (for pgvector) and a logged-in Claude Code CLI are needed for later milestones.

```bash
uv sync                      # creates .venv with Python 3.12 and all dependencies
uv run pre-commit install    # runs format, lint, types and tests before each commit
uv run pytest                # test suite; needs no network, Docker or LLM
uv run finbench run --config configs/smoke.yaml   # writes a run directory under runs/
```

## Data

FinanceBench (Islam et al., 2023, patronus-ai/financebench) is used for non-commercial research only. Its questions and filings are downloaded locally and are never committed to this repository.
