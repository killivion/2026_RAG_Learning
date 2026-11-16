import math

import pytest

from finbench.evaluation import (
    all_evidence_recall_at_k,
    ndcg_at_k,
    percentile,
    recall_at_k,
    reciprocal_rank,
)

A, B, C, D = ("F", 0), ("F", 1), ("F", 2), ("F", 3)


def test_perfect_ranking_scores_one_everywhere() -> None:
    ranking, evidence = [A, B, C], {A}

    assert recall_at_k(ranking, evidence, 1) == 1.0
    assert all_evidence_recall_at_k(ranking, evidence, 1) == 1.0
    assert reciprocal_rank(ranking, evidence) == 1.0
    assert ndcg_at_k(ranking, evidence, 1) == 1.0


def test_missing_evidence_page_gives_no_hit() -> None:
    ranking, evidence = [A, B, C], {D}

    assert recall_at_k(ranking, evidence, 3) == 0.0
    assert all_evidence_recall_at_k(ranking, evidence, 3) == 0.0
    assert reciprocal_rank(ranking, evidence) == 0.0
    assert ndcg_at_k(ranking, evidence, 3) == 0.0


def test_hit_only_counts_within_the_top_k() -> None:
    ranking, evidence = [A, B, C], {C}

    assert recall_at_k(ranking, evidence, 2) == 0.0
    assert recall_at_k(ranking, evidence, 3) == 1.0
    assert reciprocal_rank(ranking, evidence) == pytest.approx(1 / 3)


def test_any_evidence_page_is_a_hit_but_all_evidence_needs_every_page() -> None:
    ranking, evidence = [A, B, C, D], {B, D}

    assert recall_at_k(ranking, evidence, 2) == 1.0
    assert all_evidence_recall_at_k(ranking, evidence, 2) == 0.0
    assert all_evidence_recall_at_k(ranking, evidence, 4) == 1.0
    assert reciprocal_rank(ranking, evidence) == 0.5


def test_ndcg_discounts_by_rank_and_normalises_by_the_ideal_ranking() -> None:
    ranking, evidence = [A, B, C, D], {B, D}

    # DCG = 1/log2(3) + 1/log2(5); ideal DCG = 1/log2(2) + 1/log2(3).
    expected = (1 / math.log2(3) + 1 / math.log2(5)) / (1 + 1 / math.log2(3))
    assert ndcg_at_k(ranking, evidence, 4) == pytest.approx(expected)
    assert ndcg_at_k(ranking, evidence, 4) == pytest.approx(0.6509, abs=1e-4)


def test_same_page_number_in_another_filing_is_not_a_hit() -> None:
    assert recall_at_k([("OTHER", 0)], {A}, 1) == 0.0


def test_percentile_interpolates_between_values() -> None:
    values = [0.1, 0.2, 0.3, 0.4]

    assert percentile(values, 50) == pytest.approx(0.25)
    assert percentile(values, 100) == pytest.approx(0.4)
    assert percentile([0.7], 95) == pytest.approx(0.7)
