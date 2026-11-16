"""Retrieval: chunk rankings for a question, and their conversion to page rankings (ADR-0002)."""

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from rank_bm25 import BM25Okapi

from finbench.chunking import Chunk
from finbench.evaluation import PageRef

_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float


class Retriever(Protocol):
    def retrieve(self, query: str, filing: str | None, depth: int) -> list[ScoredChunk]:
        """The best `depth` chunks, best first. `filing` set means filing-scoped search."""
        ...


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class _Bm25Index:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self._bm25 = BM25Okapi([_tokenize(chunk.text) for chunk in chunks])

    def search(self, query: str, depth: int) -> list[ScoredChunk]:
        scores = self._bm25.get_scores(_tokenize(query))
        best = np.argsort(-scores, kind="stable")[:depth]
        # A score of zero means no query word occurs in the chunk: not retrieved.
        # (On a corpus of a few chunks BM25Okapi can score a matching chunk below zero,
        # which also drops it; real filings are far too large for that.)
        return [ScoredChunk(self._chunks[i], float(scores[i])) for i in best if scores[i] > 0]


class BM25Retriever:
    """BM25 over one shared index of all chunks, and over one index per filing (ADR-0003).

    All indexes are built up front, so that retrieval latency never includes index building.
    """

    def __init__(self, chunks: list[Chunk]) -> None:
        self._shared = _Bm25Index(chunks)
        by_filing: defaultdict[str, list[Chunk]] = defaultdict(list)
        for chunk in chunks:
            by_filing[chunk.filing].append(chunk)
        self._per_filing = {filing: _Bm25Index(own) for filing, own in by_filing.items()}

    def retrieve(self, query: str, filing: str | None, depth: int) -> list[ScoredChunk]:
        index = self._shared if filing is None else self._per_filing[filing]
        return index.search(query, depth)


def to_page_ranking(ranking: list[ScoredChunk]) -> list[tuple[PageRef, float]]:
    """Pages ordered by the score of their best chunk; each page appears once."""
    best: dict[PageRef, float] = {}
    for scored in ranking:
        for page in range(scored.chunk.first_page, scored.chunk.last_page + 1):
            ref = (scored.chunk.filing, page)
            best[ref] = max(best.get(ref, scored.score), scored.score)
    return sorted(best.items(), key=lambda item: -item[1])
