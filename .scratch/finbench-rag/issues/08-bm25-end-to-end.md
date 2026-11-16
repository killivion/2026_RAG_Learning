# 08: BM25 retrieval end to end

**What to build:** The first complete retrieval path. A fixed-size chunker with overlap produces chunks that carry their filing and page span. A BM25 retriever (`rank-bm25`, ADR-0003) searches the shared index or does filing-scoped search, and returns the top 50 chunks, which are cached per question and config. The chunk ranking becomes a page ranking (ADR-0002). Retrieval metrics are computed and written to the run directory:
- recall@k with any evidence page counting as a hit;
- all-evidence recall@k;
- MRR;
- nDCG@k.

A run can be retrieval-only (no generation).

**Blocked by:** 05, 06

**Status:** done

- [x] `finbench run --config <bm25 config> --split dev` writes per-question page rankings and retrieval metrics for k in {1, 3, 5, 10}, plus p50 and p95 retrieval latency
- [x] Both scopes (shared index, filing-scoped search) work by config
- [x] Runner test on the made-up filings (Seam 1): the run directory, the metrics, and cache reuse on rerun
- [x] Metric tests on hand-computed cases (Seam 2): perfect ranking gives MRR 1, a missing evidence page gives no hit, a page with several chunks is counted once

## Comments

- 2026-11-16: Implemented. New modules: `chunking.py` (fixed-size chunker), `retrieval.py` (BM25 retriever, page-ranking conversion), `evaluation.py` (retrieval metrics). `runner.py` now runs retrieval for a split and writes `questions.jsonl` next to `metrics.json`. New dependency: `rank-bm25`.
- **Dev results, PyMuPDF, 300-word chunks with 50 words overlap (51 questions):**

  | Config | recall@1 | recall@3 | recall@5 | recall@10 | all-evidence recall@10 | MRR | nDCG@10 | latency p50 |
  |---|---|---|---|---|---|---|---|---|
  | `bm25-shared` | 0.098 | 0.118 | 0.118 | 0.157 | 0.157 | 0.114 | 0.119 | 0.30 s |
  | `bm25-filing` | 0.137 | 0.196 | 0.294 | 0.412 | 0.333 | 0.211 | 0.238 | 0.003 s |

  Run directories: `runs/20261116T185955249647Z_bm25-shared_dev_1024dc9c32ad` and `runs/20261116T190026127454Z_bm25-filing_dev_c4f7d7fb3a29` (git-ignored; rerun with the configs in `configs/`).
- **The numbers are low, and that was checked.** As a control, each of the first 25 dev questions was run with its own evidence text as the query: the evidence page then ranks first to fourth every time. So parsing, chunking, page numbers and metrics line up. The weak part is the query: FinanceBench questions are long and name a metric ("fixed asset turnover ratio"), while the evidence page is a balance sheet that never uses those words. For 15 of those 25 questions the evidence page is not among the top 50 chunks at all. This is the baseline that dense retrieval (ticket 10) has to beat.
- **Design choices:**
  - Chunks are word windows that may cross page boundaries. A chunk that covers two pages gives both pages its score, so the two pages tie; ties keep page order.
  - Filing-scoped search uses its own BM25 index per filing, so word statistics (IDF) come from that filing alone. The shared index is one index over all 84 filings, dev and test companies alike; it uses no labels.
  - Tokens are lower-cased runs of letters and digits. There is no stop-word list and no stemming.
  - A chunk with a BM25 score of zero (no query word in it) is not returned, so a page ranking can be shorter than 50 chunks.
  - All-evidence recall@k is 1 only when every evidence page is in the top k pages.
  - Candidates are cached in `cache/candidates/<hash>/<question id>.json`, where the hash covers parser, chunker, chunk size, overlap, retriever and scope. The cache holds chunk ids, page spans and scores, not chunk text.
  - A cached run reports the latency of the original retrieval.
  - New config fields: `chunk_size` and `chunk_overlap` (in words, defaults 300 and 50). The defaults are placeholders, not tuned; chunking is compared in M3.
  - Every run is retrieval-only for now, so no config field for it exists yet. M2 adds the condition.
- `finbench run` now needs the downloaded data and the split; `run_experiment` takes the project root.
