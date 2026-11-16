# 08: BM25 retrieval end to end

**What to build:** The first complete retrieval path. A fixed-size chunker with overlap produces chunks that carry their filing and page span. A BM25 retriever (`rank-bm25`, ADR-0003) searches the shared index or does filing-scoped search, and returns the top 50 chunks, which are cached per question and config. The chunk ranking becomes a page ranking (ADR-0002). Retrieval metrics are computed and written to the run directory:
- recall@k with any evidence page counting as a hit;
- all-evidence recall@k;
- MRR;
- nDCG@k.

A run can be retrieval-only (no generation).

**Blocked by:** 05, 06

**Status:** ready-for-agent

- [ ] `finbench run --config <bm25 config> --split dev` writes per-question page rankings and retrieval metrics for k in {1, 3, 5, 10}, plus p50 and p95 retrieval latency
- [ ] Both scopes (shared index, filing-scoped search) work by config
- [ ] Runner test on the made-up filings (Seam 1): the run directory, the metrics, and cache reuse on rerun
- [ ] Metric tests on hand-computed cases (Seam 2): perfect ranking gives MRR 1, a missing evidence page gives no hit, a page with several chunks is counted once
