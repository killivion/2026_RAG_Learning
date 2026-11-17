# finbench-rag

Question answering over SEC filings with retrieval, evaluated on FinanceBench. The project asks research questions, not just "does it work": how much retrieval helps over the model's own knowledge, where answers fail, and whether the system knows when it doesn't know. Every choice is made on a dev split and reported once on a held-out test split.

**Status:** milestone 1 of 5 (data and retrieval baselines). The BM25 baseline runs end to end; dense retrieval with pgvector is next. Scope and milestones: [`.scratch/finbench-rag/spec.md`](.scratch/finbench-rag/spec.md).

## Results so far

Retrieval on the dev split (51 questions), BM25 over 300-word chunks with 50 words overlap:

| Config | recall@1 | recall@5 | recall@10 | all-evidence recall@10 | MRR | latency p50 |
|---|---|---|---|---|---|---|
| BM25, shared index | 0.098 | 0.118 | 0.157 | 0.157 | 0.114 | 0.30 s |
| BM25, filing-scoped search | 0.137 | 0.294 | 0.412 | 0.333 | 0.211 | 0.003 s |

These are single dev runs without confidence intervals yet. BM25 is weak here because the questions name metrics in words that the evidence pages, mostly financial statements, do not contain. Every k and the run behind each row: [`results/retrieval_runs.csv`](results/retrieval_runs.csv).

## How it works

`download → split → parse → chunk → retrieve → page ranking → metrics`, driven by one config file per run. Generation, grading and uncertainty follow in later milestones.

- **Evaluation protocol.** The 150 questions are split once into dev (51 questions, 10 companies) and test (99 questions, 22 companies), grouped by company and balanced by question type ([ADR-0001](docs/adr/0001-company-grouped-evaluation-protocol.md)). The split is committed in `splits/financebench.json` and frozen. The runner refuses the test split unless `--final` is given and the config's hash is in the committed `configs/frozen.txt`.
- **Parsing.** Filings are parsed page by page with zero-indexed page numbers. An alignment check matches all 189 evidence pages to their parsed pages. PyMuPDF is the default parser: pdfplumber retrieves no better on dev and is about 77 times slower ([`results/parser_comparison.csv`](results/parser_comparison.csv)).
- **Retrieval.** Chunks are retrieved with BM25 ([ADR-0003](docs/adr/0003-bm25-via-rank-bm25-not-postgres-fts.md)), from one shared index or restricted to the question's filing. Each chunk ranking becomes a page ranking, and all metrics count pages ([ADR-0002](docs/adr/0002-page-level-metrics-and-worst-evidence-page-score.md)). The top 50 candidates per question are cached.
- **LLM calls** go through headless Claude Code on a Claude subscription, behind a swappable backend with a disk cache ([ADR-0005](docs/adr/0005-llm-calls-through-claude-code-headless.md)). Reported cost is notional: list price, not money spent.

Each run writes a self-contained directory under `runs/`: config, manifest (config hash, git commit, split), metrics and one record per question.

## Reproduce

Requirements: [uv](https://docs.astral.sh/uv/), git, a logged-in Claude Code CLI, and Docker (for pgvector, from milestone 1 on).

```bash
uv sync                      # Python 3.12 environment with all dependencies
uv run pre-commit install    # format, lint, types and tests before each commit
uv run pytest -m "not data"  # tests without the downloaded data; no network, Docker or LLM
uv run finbench download     # questions, annotations and 84 filings (about 165 MB), checksum-verified
uv run finbench data-summary # counts of questions, companies, filings and evidence pages
uv run finbench parse-check  # parses the filings and checks pages against evidence pages
uv run finbench run --config configs/bm25_filing.yaml   # retrieval run on dev
uv run finbench summarize    # rewrites results/retrieval_runs.csv from runs/
uv run finbench parse-compare  # both parsers; pdfplumber needs about 45 minutes
uv run finbench llm-ping     # one real Claude call; the second is served from the cache
uv run pytest -m live        # opt-in test that makes one real LLM call
```

`finbench split` is only needed if `splits/financebench.json` is missing; it refuses to overwrite the frozen split.

## Repository map

| Path | What it holds |
|---|---|
| `src/finbench/` | `dataset` (download, questions, split), `parsing`, `chunking`, `retrieval`, `evaluation` (metrics), `runner`, `summary`, `llm`, `cli` |
| `configs/` | one YAML file per config, and `frozen.txt`, the configs allowed on test |
| `results/` | committed result tables; every reported number comes from here |
| `splits/` | the frozen dev/test split (question ids only) |
| `docs/adr/` | decisions that are hard to reverse |
| `GLOSSARY.md` | the project's vocabulary |
| `NOTES.md` | learning notes and the two-minute pitch |
| `.scratch/finbench-rag/` | spec and tickets |

## Data

FinanceBench (Islam et al., 2023, [patronus-ai/financebench](https://github.com/patronus-ai/financebench)) is used for non-commercial research only. `finbench download` fetches the questions, document metadata, the 16 human-annotated completion files and the 84 filings into the git-ignored `data/` and `pdfs/` folders; none of it is committed. Every file is checked against `src/finbench/financebench_manifest.json`, which pins one upstream commit and holds each file's git blob hash.
