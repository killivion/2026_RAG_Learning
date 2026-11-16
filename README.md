# finbench-rag

Retrieval-augmented question answering over SEC filings, evaluated on FinanceBench with held-out results, confidence intervals and uncertainty estimates. Work in progress: see `.scratch/finbench-rag/spec.md` for scope and `.scratch/finbench-rag/issues/` for tickets.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/) and git. Docker (for pgvector) and a logged-in Claude Code CLI are needed for later milestones.

```bash
uv sync                      # creates .venv with Python 3.12 and all dependencies
uv run pre-commit install    # runs format, lint, types and tests before each commit
uv run pytest -m "not data"  # test suite without the downloaded data; no network, Docker or LLM
uv run finbench download     # FinanceBench questions, annotations and 84 filings (about 165 MB)
uv run finbench data-summary # counts of questions, companies, filings and evidence pages
uv run finbench split        # only needed if splits/financebench.json is missing
uv run finbench parse-check  # parses the filings and checks pages against evidence pages
uv run finbench run --config configs/bm25_filing.yaml   # retrieval run on dev; writes runs/<run>/
uv run finbench parse-compare  # both parsers; pdfplumber needs about 45 minutes
uv run finbench summarize    # rewrites results/retrieval_runs.csv from runs/
uv run finbench llm-ping     # one real Claude call through Claude Code; the second run is cached
uv run pytest -m live        # opt-in test that makes one real LLM call
```

## Parsing

Filings are parsed page by page with zero-indexed page numbers, behind one parser interface, and cached per parser and filing under `cache/parsed/`. `finbench parse-check` fuzzy-matches every evidence page's FinanceBench text against the parsed page with the same number. With PyMuPDF, all 189 evidence pages match (similarity of at least 90 of 100), and every one matches page n better than pages n-1 and n+1, which confirms the zero-indexing. FinanceBench's texts were very likely extracted with PyMuPDF too, so this confirms page alignment rather than parsing quality.

PyMuPDF is the default parser. pdfplumber gives the same BM25 retrieval on dev within noise (recall@10 of 0.157 against 0.157 on the shared index, 0.373 against 0.412 with filing-scoped search, a gap of two questions) and takes 43 minutes instead of 34 seconds to parse the 84 filings. `finbench parse-compare` writes the alignment and timing table to `results/parser_comparison.csv`.

## Retrieval

A run parses and chunks all 84 filings, retrieves the top 50 chunks for every question of the split, and turns each chunk ranking into a page ranking, in which a page takes the score of its best chunk (`docs/adr/0002`). All metrics count pages. The run directory holds the config, a manifest (config hash, git commit, split), `metrics.json` and one record per question in `questions.jsonl`. Candidates are cached, so a rerun retrieves nothing again; a cached question keeps the latency of its original retrieval. The index always covers all 84 filings, including those of test companies. That uses no labels: it is the document collection, and only questions and evidence pages are held out.

First baseline on dev (51 questions): BM25 (`rank-bm25`, `docs/adr/0003`) over 300-word chunks with 50 words overlap, parsed with PyMuPDF.

| Config | recall@1 | recall@5 | recall@10 | all-evidence recall@10 | MRR | latency p50 |
|---|---|---|---|---|---|---|
| BM25, shared index | 0.098 | 0.118 | 0.157 | 0.157 | 0.114 | 0.30 s |
| BM25, filing-scoped search | 0.137 | 0.294 | 0.412 | 0.333 | 0.211 | 0.003 s |

The full table, with every k and the run directory behind each row, is `results/retrieval_runs.csv`; `finbench summarize` rewrites it from the run directories. These are dev numbers from one run each, without confidence intervals yet. BM25 is weak here because the questions name metrics in words that the evidence pages (mostly financial statements) do not contain.

## Evaluation protocol

The 150 questions are split once into dev (51 questions, 10 companies) and test (99 questions, 22 companies). The split is grouped by company, so no company's filings are both tuned on and tested on, and each question type has the same share on both sides (`docs/adr/0001`). It is committed as `splits/financebench.json` and frozen: `finbench split` refuses to overwrite it. That file is the source of truth; the seed in it only records how it was made. `--force` exists, but using it after any dev result has been seen is a protocol violation, because the test questions would no longer be held out.

The runner refuses the test split unless `--final` is given and the config's hash is listed in the committed `configs/frozen.txt`. That list is empty until the configs are frozen in M3.

## LLM calls

Every LLM call goes through headless Claude Code on a Claude subscription, behind a swappable backend (`src/finbench/llm.py`, `docs/adr/0005`). Calls are cached on disk under `cache/llm/<backend>/`, keyed by model, prompts, schema and prompt version, so a rerun costs no usage and an interrupted run resumes. Reported cost is notional: list-price cost as the CLI reports it, not money spent.

## Data

FinanceBench (Islam et al., 2023, patronus-ai/financebench) is used for non-commercial research only. `finbench download` fetches the 150 questions, the document metadata, the 16 human-annotated completion files and the 84 filings into the git-ignored `data/` and `pdfs/` folders. They are never committed to this repository.

Every file is checked against `src/finbench/financebench_manifest.json`, which pins one upstream commit and holds each file's git blob hash. A rerun skips files that match and stops on any mismatch.
