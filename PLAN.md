# PLAN.md: finbench-rag

## One-paragraph summary

Build a retrieval-augmented QA system over SEC filings and measure it rigorously. Using FinanceBench (150 human-annotated questions, each with gold answer, source document and zero-indexed evidence page), the project answers three things:

- which retrieval choices actually help, with held-out results and confidence intervals;
- how much of answer quality comes from retrieval versus what the LLM already memorized;
- whether the system can tell when it doesn't know, through calibrated confidence, risk-coverage curves and conformal retrieval with a coverage guarantee.

## Research questions

**Retrieval**
1. Does hybrid retrieval (BM25 + dense, reciprocal rank fusion) beat each component alone? By how much on held-out data?
2. Which chunking strategy (fixed-size, page-level, structure-aware with intact tables) works best on table-heavy filings?
3. What does a cross-encoder reranker add, at what latency and cost?
4. Does restricting search to the named filing beat one shared index?

**Generation and error attribution**

5. Ladder: closed-book, then RAG, then oracle (gold page given). How much of accuracy is memorization, how much is retrieval's contribution, and what is the ceiling?
6. What share of errors are retrieval misses, ranking errors, table parsing, arithmetic, or hallucination despite correct context?

**Uncertainty**

7. Which confidence signal best separates right from wrong answers?
8. What accuracy does the system reach at 80% or 90% coverage? Report the full risk-coverage curve.
9. Does conformal retrieval reach its nominal gold-page coverage on held-out questions, and how many pages does it need on average?

**Evaluation methodology (optional, week 5)**

10. Do synthetic LLM-generated questions rank pipeline configs the same way human questions do (Kendall's tau)?

## Data and splits

- Source: FinanceBench open sample from the patronus-ai/financebench GitHub repo. Checked on 2026-11-16:
  - 150 questions over 32 companies (1 to 11 questions each) and 84 filings. The question types are 50 metrics-generated, 50 domain-relevant and 50 novel-generated.
  - 115 questions have 1 evidence page, 31 have 2 and 4 have 3. No question draws evidence from more than one filing.
  - About 52 gold answers are plain numbers; the rest are free text.
  - The repo holds 368 PDFs (0.71 GB), of which the 84 used filings are 0.17 GB.
- License: the repo has **no LICENSE file**, and the GitHub API reports none. The paper's dataset card names CC-BY-NC-4.0. This project lives in a **private** GitHub repo, for showcasing only:
  - `data/` and `pdfs/` are git-ignored, so FinanceBench content is never committed.
  - The CLI downloads them with checksums.
  - The README credits the paper and states that the data is non-commercial and not redistributed.
- The repo also has 16 files of human-annotated model completions (150 rows each, labelled "Correct Answer" / "Incorrect Answer"). These validate the grader.
- **Splits, created once and frozen** (see `docs/adr/0001`):
  - dev about 50 questions, test about 100.
  - Grouped by company, so no company appears in both. Question types are balanced across the splits.
  - Fixed seed; the split file is committed.
- Every choice is made on dev. Test is only for reporting.
- Conformal calibration happens inside the test split via repeated calibration/evaluation splits, also grouped by company (see below). Calibration uses only cached scores, never re-tuned configs.

## Pipeline

Each stage is a Protocol with swappable implementations selected by config.

1. **Ingest.** Parse PDFs page by page, keeping page numbers. Compare two parsers (e.g. PyMuPDF and pdfplumber).
   - Parser quality is the fuzzy-match rate of FinanceBench's `evidence_text` and `evidence_text_full_page` against the parser's text for that page. There is no table ground truth, so this is the proxy.
   - The same check is the alignment test: it verifies the zero-indexing (page 0 is the cover page).
2. **Chunk.** Fixed-size with overlap, page-level, and structure-aware chunking that keeps tables intact. Every chunk carries a document id and its page span.
3. **Index.** Postgres + pgvector for dense vectors. `rank-bm25` in-process for sparse retrieval, because Postgres `ts_rank` is not BM25 (see `docs/adr/0003`). Embeddings are computed once per (chunking config, embedding model) and stored.
4. **Retrieve.** BM25, dense, hybrid via RRF. Options: shared index vs. filing-scoped search. Retrieve the top 50 chunks and cache the candidates.
   - Each chunk ranking becomes a **page ranking**: a page takes its best chunk's score, and k counts pages (see `docs/adr/0002`).
   - The shared index holds the 84 filings our questions use. They already include the hardest distractors: the same company's other years. The full 368-filing index is optional after M5.
5. **Rerank.** Cross-encoder over the cached top 50, keep the top k.
6. **Generate.** Claude with a structured output: answer, cited chunk ids, self-reported confidence, abstain flag. Plus two extra conditions:
   - **Closed-book:** no context at all, measures memorization.
   - **Oracle:** all of the question's evidence pages given directly, measures the generation ceiling.
7. **Grade.**
   - Numeric: a question is graded numerically when its gold answer parses as a single number. Deterministic parsing with unit and percent normalisation, 1% relative tolerance.
   - Free text: LLM judge, validated as described below.
   - An abstention counts as incorrect at full coverage.

Models:
- Generator: `claude-sonnet-5-5`.
- Judge: a different Claude version (R2-Q3), the same family by choice (see `docs/adr/0004`).
- Embedding model and cross-encoder: pick one small open model of each from current leaderboards (e.g. MTEB). Pin exact identifiers in config, and note the reason in the milestone's learning note.

## Metrics

- **Retrieval:** on the page ranking: recall@k (a hit means any evidence page is in the top k), all-evidence recall@k, MRR, nDCG@k.
- **Answers:** accuracy (numeric with tolerance, else judged), citation precision (does a cited chunk contain the evidence page?), abstention rate.
- **Cost:** tokens, € per query, p50/p95 latency.
- **Statistics:** paired bootstrap confidence intervals for differences between configs; McNemar's test for paired correct/incorrect outcomes.
- **Uncertainty:** reliability diagram, Brier score, ECE, AUROC of confidence for separating right from wrong, risk-coverage curve and its area (AURC).

## Uncertainty layer

### Confidence signals (RQ7)

| Signal | How it's computed | Extra cost |
|---|---|---|
| Reranker top score | Already computed | None |
| Retrieval margin | Top-1 minus top-2 score | None |
| Self-reported | Field in the structured output | About zero |
| Self-consistency | N=5 samples, agreement rate | 5x generation cost |
| Abstain flag | Field in the structured output | None |

Run self-consistency only on the final frozen config, not across the whole grid. Any preference between signals is formed on dev. On test, all signals are reported and no winner is picked there.

### Selective prediction (RQ8)

For each signal, sort the test questions by confidence and compute accuracy over the top x% for every x. Always report full-coverage accuracy next to any selective result.

### Conformal retrieval (RQ9)

This is split conformal prediction. No model is trained.

1. Nonconformity score for a question = rank of the worst-ranked evidence page in the reranked page ranking. If any evidence page isn't among the candidates, the score is infinite.
2. Randomly split the test questions into calibration and evaluation halves, grouped by company.
3. On the calibration half, take the ceil((n+1)(1-alpha))/n empirical quantile of the scores. That rank is the threshold q.
4. On the evaluation half, return all pages ranked up to q and record two things: whether the gold page is included, and how many pages were returned.
5. Repeat steps 2 to 4 about 1000 times. Report the distribution of achieved coverage and of set size, for alpha in {0.1, 0.2}.
6. Variant with an adaptive set size: use a score-based threshold (reranker score) instead of rank, so easy questions get fewer pages.

Because all scores are cached, this whole step takes seconds. If more than alpha of the calibration questions have an infinite score, q is infinite and the method returns every candidate page. Report that outcome as is, since it is itself a finding about retrieval.

## Grader validation (leakage-proof)

- Use the human-annotated model completions shipped with FinanceBench.
- Split them following the question split: completions on dev questions are for prompt tuning, completions on test questions are for measuring agreement.
- Tune the judge prompt on dev only, then freeze it. Report agreement on test (accuracy, Cohen's kappa, confusion matrix).
- The judge is a different Claude version from the generator (same family, by choice). Self-preference bias is stated as a limitation.
- The judge sees question, gold answer and candidate answer, never the config name or retrieved context.

## Milestones

Each milestone ends with:
- tests green;
- its `.scratch/` issues resolved;
- new terms in `GLOSSARY.md` and any hard-to-reverse decision as an ADR in `docs/adr/`;
- a learning note in `learning/` and an updated `learning/00-pitch.md` (format in `learning/README.md`);
- committed and pushed results.

Tickets: M0 and M1 are broken into `.scratch/` issues with `/to-tickets`. Each later milestone gets its tickets when the previous milestone is done, because its details depend on earlier results.

**M0 Setup (0.5 to 1 day)**
- Git repo with remote `github.com/killivion/2026_RAG_Learning` (private).
- uv project with src layout, ruff, mypy, pytest, pre-commit, GitHub Actions CI.
- docker compose for pgvector, `.env.example`, Typer CLI skeleton, pydantic config model, run-directory writer, disk cache for API calls.
- Done when: `uv run pytest` and CI pass on an empty skeleton, and `docker compose up -d` gives a working pgvector.

**M1 Data and baselines (week 1)**
- Download with checksums, frozen grouped splits, ingestion with page tracking and alignment tests.
- Fixed-size chunking, BM25 and dense retrieval, retrieval metrics.
- Done when: dev recall@k and MRR for BM25 and dense are reported, and the alignment test passes on all evidence pages.

**M2 Full pipeline (week 2)**
- Hybrid search, reranker, all chunking variants, generation with citations.
- Closed-book and oracle conditions, numeric grader, validated LLM judge.
- Done when: the closed-book / RAG / oracle ladder is reported on dev, and judge agreement on held-out annotations is reported.

**M3 Ablations and final test run (week 3)**
- Ablation grid on dev, Pareto plot, error taxonomy (hand-label dev failures), freeze 2 or 3 configs.
- Run `--final` once on test, with bootstrap CIs and McNemar's tests.

**M4 Uncertainty (week 4)**
- Confidence signals, calibration plots, risk-coverage curves.
- Conformal retrieval with repeated grouped splits, timeboxed to one day.

**M5 Report (week 5)**
- README as a short technical report: results tables first, then methods, limitations and reproduction steps.
- Optional: synthetic-vs-human eval study (RQ10).

**Optional after M5:**
- FastAPI wrapper plus a TypeScript UI with a query view and results explorer.
- The experiment agent searching the config space.
- A robustness run of the frozen configs on a shared index of all 368 filings in the repo.

## Known limitations to state openly

- n=150, so effects need large sizes to be significant. Report CIs, not just point estimates.
- FinanceBench questions are designed to be clear-cut, so results may not transfer to ambiguous analyst questions.
- Closed-book accuracy is a lower bound on memorization, not a measure of it. FinanceBench has been public since 2023, so its gold answers may be in the generator's training data.
- The judge comes from the same model family as the generator (self-preference bias).
- With about 20 test companies, the grouped conformal splits give a wide coverage distribution.
- The conformal guarantee assumes new questions are exchangeable with the calibration questions.

## Where things are recorded

- `GLOSSARY.md`: project vocabulary. Use these terms in code, issues and the report.
- `docs/adr/`: hard-to-reverse decisions and their reasons.
- `.scratch/<feature>/`: specs and issues (local issue tracker, see `docs/agents/issue-tracker.md`).
- `learning/`: my own learning notes, one per concept or milestone.
- `README.md`: the technical report (M5).

## Open decisions

- Embedding model and cross-encoder ids (M1, pinned in config).
- Exact dev/test sizes after the grouped split (M1).
- Still being grilled: how the LLM is accessed (API key vs Pro subscription), which sets the generator and judge ids and the budget cap.
