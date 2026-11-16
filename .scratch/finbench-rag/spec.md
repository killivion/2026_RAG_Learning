# Spec: finbench-rag

Status: ready-for-agent

Vocabulary follows `GLOSSARY.md`. Decisions follow `docs/adr/0001`–`0005`.

## Problem Statement

I want to learn retrieval-augmented generation properly and show that I can evaluate it like a researcher, not just build a demo. Most RAG showcases report one accuracy number on questions the author also tuned on. They can't say whether retrieval helped at all, or whether the model already knew the answer. They can't say when the system should not be trusted.

I need a project over a real, hard domain (SEC filings, which are full of tables) with a human-labelled benchmark (FinanceBench). It should answer clear research questions with held-out results, confidence intervals and honest limitations. It must run on my Claude Pro subscription without extra spending, live in a private GitHub repo, and leave me with notes I can use to explain every concept in an interview.

## Solution

A Python research codebase, driven from a command line, that:

1. Downloads the FinanceBench open sample and its filings with checksums, and makes a frozen dev/test split grouped by company (ADR-0001).
2. Parses filings page by page, chunks them three ways, and indexes them for BM25 (`rank-bm25`, ADR-0003) and dense retrieval (pgvector). It retrieves with BM25, dense or hybrid (RRF), against a shared index or with filing-scoped search, then reranks with a cross-encoder.
3. Generates answers with Claude in three conditions (closed-book, RAG, oracle). Each answer has citations, a self-reported confidence and an abstention flag. LLM calls go through headless Claude Code on the Pro subscription, behind a swappable backend (ADR-0005).
4. Grades answers with a numeric checker and an LLM judge. The judge is validated against FinanceBench's human-annotated completions, without leakage.
5. Runs configs as cached, resumable experiments. Each run writes a self-contained run directory, and test-split runs are blocked unless the config is frozen.
6. Reports retrieval metrics, accuracy, notional cost and latency, paired bootstrap CIs and McNemar tests, calibration, risk-coverage curves and conformal retrieval.
7. Ends with a README written as a short technical report and a `learning/` folder with one note per concept.

### Research questions

**Retrieval**
- RQ1: Does hybrid retrieval beat BM25 and dense alone, on held-out data?
- RQ2: Which chunking (fixed-size, page-level, structure-aware) works best on table-heavy filings?
- RQ3: What does a cross-encoder reranker add, and at what latency?
- RQ4: Does filing-scoped search beat a shared index?

**Generation and error attribution**
- RQ5: How does accuracy change along the closed-book → RAG → oracle ladder? How much is memorization, how much is retrieval, and where is the ceiling?
- RQ6: What share of errors come from retrieval misses, ranking errors, table parsing, arithmetic, or hallucination despite correct context?

**Uncertainty**
- RQ7: Which confidence signal best separates correct from incorrect answers?
- RQ8: What accuracy do we get at 80% and 90% coverage? Report the full risk-coverage curve.
- RQ9: Does conformal retrieval reach its nominal coverage on held-out questions, and how many pages does it need?

**Optional**
- RQ10: Do synthetic questions rank configs the same way human questions do?

## User Stories

### Data
1. As the researcher, I want one command to download the FinanceBench questions, document metadata, human-annotated completions and the 84 filings, so that setup is reproducible.
2. As the researcher, I want every downloaded file checked against a recorded checksum, so that silent upstream changes are caught.
3. As the researcher, I want FinanceBench data and PDFs never committed to git, so that my private showcase repo respects the non-commercial data terms.
4. As the researcher, I want questions loaded as typed objects with their filing, gold answer, question type and evidence pages, so that downstream code never parses raw JSON.
5. As the researcher, I want a frozen dev/test split grouped by company, with question types balanced, so that no company's filings are tuned on and tested on.
6. As the researcher, I want the split created once with a fixed seed and committed, so that every run uses the same questions.
7. As the researcher, I want the split's summary (sizes, companies, type mix) printed and recorded, so that I can report it.

### Ingestion
8. As the researcher, I want each filing parsed page by page with zero-indexed page numbers, so that evidence pages line up with parsed pages.
9. As the researcher, I want two parsers behind one interface, so that I can compare them.
10. As the researcher, I want an alignment check that fuzzy-matches each evidence page's FinanceBench text against the parsed page, so that zero-indexing is verified on every evidence page.
11. As the researcher, I want each parser's match rate reported, so that I can choose a parser on evidence rather than intuition.
12. As the researcher, I want parsed pages cached per (parser, filing), so that parsing runs once.

### Chunking and indexing
13. As the researcher, I want fixed-size, page-level and structure-aware chunking behind one interface, so that RQ2 is a config switch.
14. As the researcher, I want every chunk to carry its filing and page span, so that any ranking can be turned into a page ranking.
15. As the researcher, I want tables kept whole by the structure-aware chunker, so that table-heavy evidence isn't split mid-row.
16. As the researcher, I want embeddings computed once per (chunking config, embedding model) and stored in pgvector, so that experiments don't re-embed.
17. As the researcher, I want BM25 to be real BM25, so that the baseline is labelled honestly.

### Retrieval and reranking
18. As the researcher, I want BM25, dense and hybrid (RRF) retrievers behind one interface, so that RQ1 is a config switch.
19. As the researcher, I want the choice between shared index and filing-scoped search as a config option, so that RQ4 is a config switch.
20. As the researcher, I want the top 50 candidates cached per question and config, so that reranking and conformal analysis never re-retrieve.
21. As the researcher, I want an optional cross-encoder reranker over the cached candidates, so that RQ3 is measured on identical inputs.
22. As the researcher, I want every chunk ranking turned into a page ranking (each page takes its best chunk's score), so that metrics are comparable across chunkers (ADR-0002).
23. As the researcher, I want recall@k (any evidence page), all-evidence recall@k, MRR and nDCG@k computed on page rankings, so that retrieval quality is reported consistently.
24. As the researcher, I want retrieval latency recorded per question, so that I can report p50 and p95.

### Generation
25. As the researcher, I want the generator to return structured output (answer, cited chunk ids, self-reported confidence, abstain flag), so that answers can be graded and analysed automatically.
26. As the researcher, I want closed-book, RAG and oracle conditions on the same questions, so that the RQ5 ladder is paired.
27. As the researcher, I want the oracle condition to receive all evidence pages, so that the ceiling is fair on questions with several evidence pages.
28. As the researcher, I want LLM calls to go through my Pro subscription via headless Claude Code, so that I pay nothing extra.
29. As the researcher, I want the LLM backend to be swappable by config, so that I can move to the API later without touching experiment code.
30. As the researcher, I want every LLM call cached on disk by its full request, so that reruns cost no usage and interrupted runs resume.
31. As the researcher, I want a run to stop cleanly when the subscription's usage limit is hit and to resume from the cache later, so that limits never corrupt results.
32. As the researcher, I want tokens and notional cost recorded per call, so that I can still report cost per query honestly labelled as notional.
33. As the researcher, I want prompts versioned, so that a cached answer is never reused after a prompt change.

### Grading
34. As the researcher, I want questions whose gold answer is a single number graded deterministically with unit and percent normalisation and 1% relative tolerance, so that a third of grading needs no LLM.
35. As the researcher, I want all other answers graded by an LLM judge that sees only question, gold answer and candidate answer, so that it can't be biased by the config or context.
36. As the researcher, I want the judge prompt tuned only on human annotations of dev questions and then frozen, so that judge validation doesn't leak.
37. As the researcher, I want judge agreement (accuracy, Cohen's kappa, confusion matrix) reported on annotations of test questions, so that I can trust the judge.
38. As the researcher, I want an abstention graded as incorrect at full coverage, so that abstaining never inflates accuracy.
39. As the researcher, I want citation precision computed (does a cited chunk span an evidence page?), so that grounding is measured, not assumed.

### Experiments and evaluation discipline
40. As the researcher, I want a config file to describe one complete config, validated on load, so that typos fail fast.
41. As the researcher, I want each run to write a self-contained run directory (config, git commit, split, per-question records, metrics), so that every number in the report traces back to a run.
42. As the researcher, I want the runner to refuse the test split unless the config is in a committed frozen-configs list and the final flag is given, so that test leakage is mechanically prevented.
43. As the researcher, I want an ablation grid run on dev from one command, so that M3 is cheap to repeat.
44. As the researcher, I want a Pareto plot of accuracy against latency and notional cost for dev configs, so that I can choose 2–3 configs to freeze.
45. As the researcher, I want paired bootstrap CIs and McNemar tests for differences between configs, so that I don't over-claim from 100 questions.
46. As the researcher, I want an error taxonomy file where I hand-label dev failures, so that RQ6 has a documented basis.

### Uncertainty
47. As the researcher, I want five confidence signals per answer (reranker top score, retrieval margin, self-reported, self-consistency, abstain flag), so that RQ7 compares them.
48. As the researcher, I want self-consistency run only on frozen configs, so that it doesn't use up usage limits across the grid.
49. As the researcher, I want reliability diagrams, Brier score, ECE and AUROC per signal, so that calibration and separation are both shown.
50. As the researcher, I want risk-coverage curves with AURC per signal, always next to full-coverage accuracy, so that selective results aren't cherry-picked.
51. As the researcher, I want every signal reported on test with no winner picked there, so that choosing a signal doesn't leak test information.
52. As the researcher, I want conformal retrieval with ~1000 repeated calibration/evaluation splits grouped by company, for alpha 0.1 and 0.2, so that RQ9 reports coverage and set-size distributions.
53. As the researcher, I want an infinite conformal threshold reported as "returns all candidate pages", so that retrieval misses are visible rather than hidden.
54. As the researcher, I want an adaptive variant that thresholds on reranker score, so that easy questions get smaller page sets.

### Reporting and learning
55. As a reader of the repo, I want the README to open with results tables, then methods, limitations and reproduction steps, so that I get the findings in two minutes.
56. As the researcher, I want figures generated from run directories by a command, so that the report is reproducible.
57. As the learner, I want a learning note drafted for each concept at the end of every milestone, so that I can rewrite it in my own words.
58. As the learner, I want `learning/00-pitch.md` updated every milestone, so that I always have a current two-minute pitch.
59. As the researcher, I want new terms added to `GLOSSARY.md` and hard-to-reverse decisions recorded as ADRs as they happen, so that the domain model stays current.

### Engineering
60. As the researcher, I want a uv project with ruff, mypy, pytest and pre-commit, so that quality gates run locally.
61. As the researcher, I want GitHub Actions CI on the private repo, so that every push is checked.
62. As the researcher, I want Postgres with pgvector started from one docker compose command, so that the dense index is reproducible.
63. As the researcher, I want the whole test suite to run without network, Docker or LLM access, so that CI stays fast and free.

## Implementation Decisions

### Modules (deep modules with small interfaces)

- **Dataset**: owns download, checksums, typed questions and filings, and the frozen split.
  - Interface: load the questions of a split; get a filing's path; build the split once (refuses to overwrite).
  - Split rule: grouped by company, balanced by question type, about 50 dev / 100 test, fixed seed.
- **Parsing**: a `Parser` protocol turns a filing into zero-indexed page texts. Two implementations (PyMuPDF and pdfplumber), with results cached. An alignment/fidelity function scores a parser by fuzzy-matching evidence texts against its pages.
- **Chunking**: a `Chunker` protocol turns page texts into chunks with filing id and page span. Implementations: fixed-size with overlap, page-level, structure-aware with whole tables.
- **Retrieval**: a `Retriever` protocol returns a chunk ranking for a question, a scope (shared index or a filing id) and a depth. Implementations: BM25 (`rank-bm25`, in-process), dense (pgvector), hybrid (RRF over the two). Page-ranking conversion is one shared function.
- **Reranking**: a `Reranker` protocol reorders a cached candidate list. Implementations: identity and cross-encoder.
- **LLM backend**: an `LLMBackend` protocol takes model, system prompt, user prompt and JSON schema, and returns parsed output, token usage, notional cost and latency.
  - Implementations: headless Claude Code (single turn, no tools, custom system prompt, schema-validated JSON, no session persistence) and a scripted fake for tests. An API backend may be added later.
  - A caching layer wraps any backend. The cache key covers model, prompts, schema and prompt version.
  - Usage-limit errors surface as one specific exception that stops the run cleanly.
- **Generation**: builds the prompt for a condition (closed-book, RAG, oracle) and returns an `Answer`: answer text, cited chunk ids, confidence 0–1, abstain flag.
- **Grading**: decides numeric vs judged per question from the gold answer, and returns a grade with its method.
  - The judge has its own versioned prompt and sees no config or context.
  - A validation routine scores the judge against human-annotated completions for a given split.
- **Experiment runner**: the highest seam.
  - Input: a validated config plus a split. Output: a run result and run directory.
  - It wires stages from config, caches candidates, answers and grades per question, records git commit and config hash, and resumes after interruption.
  - Test-split guard: allowed only with the final flag and a config hash in the committed frozen-configs list.
- **Evaluation**: pure functions over per-question records.
  - Retrieval metrics on page rankings; accuracy; citation precision; abstention rate.
  - Paired bootstrap and McNemar.
  - Calibration (reliability bins, Brier, ECE, AUROC), risk-coverage and AURC.
  - Split conformal over nonconformity scores (worst evidence-page rank, infinite when missing), with repeated grouped splits and the adaptive score-threshold variant.
- **CLI**: a thin Typer app with commands for download, split, parse-check, index, run, grid, final, figures and judge-validate. No logic beyond argument parsing.
- **Config**: one pydantic model for a config (parser, chunker, retriever, scope, reranker, k, prompt version, generator and judge model ids, backend, max LLM calls per run). Pinned embedding and cross-encoder ids are chosen in M1 from a current leaderboard, and the reason goes in a learning note.

### Models and budget
- Generator `claude-sonnet-5-5`, judge `claude-haiku-5-5`: same family, different version (ADR-0004, ADR-0005).
- The budget is a maximum number of uncached LLM calls per run, to stay inside Pro usage windows. Notional cost is reported, never spent.

### Data handling
- Data, PDFs, caches and runs are git-ignored.
- Run directories are summarised into committed result tables (CSV/JSON) that hold no FinanceBench text beyond question ids.

### Process
- Scope lives in this spec; its tickets live in this directory's `issues/` folder.
- Milestone order: M0 setup, M1 data and baselines, M2 full pipeline, M3 ablations and final test run, M4 uncertainty (conformal timeboxed to one day), M5 report.
- Only M0 and M1 are ticketed now; each later milestone is ticketed when the previous one closes.

## Testing Decisions

- **What makes a good test**: it exercises behaviour through a public interface and asserts on outputs a user of the module would care about. It never asserts on private helpers, call order or internal data structures, and it survives a refactor of the internals.
- **Seam 1, experiment runner (primary).** End-to-end tests run a config against a tiny fixture corpus: two synthetic filings of a few pages, a handful of questions, an in-memory dense retriever stand-in and the scripted fake LLM backend. They assert on:
  - the run directory and metrics;
  - resume after a simulated usage-limit stop;
  - cache hits on rerun;
  - test-split refusal without a frozen config.
- **Seam 2, evaluation functions.** Metrics, statistics, calibration, risk-coverage and conformal are pure functions, tested against hand-computed small cases and known properties. Examples: perfect ranking gives MRR 1; on exchangeable synthetic scores, conformal coverage is at least 1−alpha on average; McNemar matches a reference value.
- **Module-level tests only where a module has its own contract worth pinning**:
  - Dataset: split is grouped and balanced, and refuses to overwrite.
  - Parsing alignment: runs on the real data only, marked as a data test that CI skips.
  - Grading: numeric normalisation table.
  - Claude Code backend: one opt-in smoke test, skipped by default, that makes a single real call.
- CI runs everything except tests marked as data or live, with no network, Docker or LLM.
- **Prior art**: none yet (empty repository). The first runner and evaluation tests set the pattern.

## Out of Scope

- The 368-filing shared index (optional after M5).
- A FastAPI wrapper, a TypeScript UI, and the experiment agent searching the config space (optional after M5).
- Synthetic-question study RQ10 (optional in M5).
- Any paid API usage; the API backend only exists if the Pro route proves unworkable.
- Fine-tuning or training any model.
- Public release of data, PDFs or FinanceBench-derived text.

## Further Notes

- **Environment facts (2026-11-16):** Claude Code 2.1.317 is installed and supports `--print`, `--json-schema`, `--system-prompt`, `--tools`, `--model` and `--no-session-persistence`. `uv` and Docker are not installed, and system Python is 3.9.5, so M0 includes a human setup ticket and uv manages a newer Python.
- **Data facts (2026-11-16):**
  - 150 questions, 32 companies, 84 filings.
  - Question types 50/50/50.
  - 35 questions have 2–3 evidence pages, all within one filing.
  - About 52 numeric gold answers.
  - 16 human-annotated completion files of 150 rows each.
  - No LICENSE file in the repo.
- **Split facts (2026-11-16, `splits/financebench.json`, seed 0):**
  - Dev: 51 questions, 10 companies, 27 filings, question types 17/17/17.
  - Test: 99 questions, 22 companies, 57 filings, question types 33/33/33.
  - No company is in both splits.
  - Dev companies: AMD, Activision Blizzard, American Express, American Water Works, Block, General Mills, JPMorgan, MGM Resorts, Paypal, PepsiCo.
- **Known limitations to state in the report:**
  - n=150, so report CIs;
  - questions are clear-cut by design;
  - closed-book is a lower bound on memorization, and contamination is likely;
  - the judge is from the same family as the generator;
  - conformal coverage assumes exchangeability, and the grouped splits are small;
  - cost is notional (Pro subscription);
  - the terms of use for automated subscription use must be checked before the M2 runs.
