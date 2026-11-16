"""Evaluation: pure functions over page rankings (ADR-0002). All metrics count pages, not chunks."""

import math
from collections.abc import Sequence, Set

PageRef = tuple[str, int]  # (filing, zero-indexed page)


def recall_at_k(ranking: Sequence[PageRef], evidence: Set[PageRef], k: int) -> float:
    """1 when any evidence page is among the top k pages (a hit), else 0."""
    return float(any(page in evidence for page in ranking[:k]))


def all_evidence_recall_at_k(ranking: Sequence[PageRef], evidence: Set[PageRef], k: int) -> float:
    """1 when every evidence page is among the top k pages, else 0."""
    return float(evidence <= set(ranking[:k]))


def reciprocal_rank(ranking: Sequence[PageRef], evidence: Set[PageRef]) -> float:
    """1 / rank of the first evidence page; 0 when none is ranked."""
    for rank, page in enumerate(ranking, start=1):
        if page in evidence:
            return 1 / rank
    return 0.0


def ndcg_at_k(ranking: Sequence[PageRef], evidence: Set[PageRef], k: int) -> float:
    """Discounted gain of the evidence pages in the top k, relative to the best possible order."""
    gain = sum(
        1 / math.log2(rank + 1)
        for rank, page in enumerate(ranking[:k], start=1)
        if page in evidence
    )
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(evidence)) + 1))
    return gain / ideal


def percentile(values: Sequence[float], percent: float) -> float:
    """The `percent`-th percentile, linearly interpolated between neighbouring values."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
