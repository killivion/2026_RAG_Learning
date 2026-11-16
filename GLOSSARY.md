# finbench-rag

Question answering over SEC filings with retrieval, measured against FinanceBench: how much retrieval helps, where answers fail, and whether the system knows when it doesn't know.

## Data

**Filing**:
One SEC document (10-K, 10-Q, 8-K or earnings release) for one company and period, identified by its FinanceBench `doc_name`.
_Avoid_: Document (ambiguous with chunk), report, PDF

**Question**:
One FinanceBench item: a natural-language question about exactly one filing, with a gold answer and one or more evidence pages.
_Avoid_: Query (reserve for what the retriever receives), sample

**Evidence page**:
A page of the question's filing that a human annotator marked as containing the answer, zero-indexed. A question has one to three of them, always in the same filing.
_Avoid_: Gold chunk, source page

**Dev split / Test split**:
The two frozen, disjoint sets of questions, grouped so that no company appears in both. Dev is for every choice; test is only for reporting.
_Avoid_: Validation set, holdout (use "test")

## Retrieval

**Chunk**:
A contiguous span of a filing's text that is indexed and retrieved as one unit; it knows its filing and page span.
_Avoid_: Passage, document, node

**Page ranking**:
The order of pages derived from a chunk ranking, where each page takes the score of its best chunk. All retrieval metrics are counted in pages, not chunks.

**Hit**:
A page ranking contains a hit at k when any evidence page of the question is among its top k pages.
_Avoid_: Match

**Shared index**:
One index over many filings, searched without knowing which filing the question is about.
_Avoid_: Global store

**Filing-scoped search**:
Retrieval restricted to the filing that the question names.
_Avoid_: Single store, filtered index

## Generation

**Condition**:
What the generator is given as context: closed-book (nothing), RAG (retrieved chunks) or oracle (all evidence pages).

**Abstention**:
The generator declining to answer. It counts as incorrect at full coverage.
_Avoid_: Refusal, no-answer

**Config**:
One complete choice of parser, chunker, retriever, reranker, k and prompt; the unit that is compared and frozen.
_Avoid_: Pipeline variant, setting

## Uncertainty

**Confidence signal**:
A per-question score meant to be higher when the answer is correct (reranker top score, retrieval margin, self-reported confidence, self-consistency, abstain flag).

**Coverage**:
In selective prediction, the fraction of questions the system answers. In conformal retrieval, the fraction of questions whose returned page set contains all evidence pages. Always say which one.

**Nonconformity score**:
For conformal retrieval, the rank of the worst-ranked evidence page in a question's page ranking; infinite if any evidence page is missing from the candidates.
