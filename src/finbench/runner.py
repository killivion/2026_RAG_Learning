"""Experiment runner: the highest test seam. Turns a config and a split into a run directory."""

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from finbench.chunking import Chunk, Chunker, FixedSizeChunker
from finbench.config import Config
from finbench.dataset import Question, Split, load_questions, load_split
from finbench.evaluation import (
    PageRef,
    all_evidence_recall_at_k,
    ndcg_at_k,
    percentile,
    recall_at_k,
    reciprocal_rank,
)
from finbench.parsing import ParserName, parse_filing
from finbench.retrieval import BM25Retriever, Retriever, ScoredChunk, to_page_ranking

CANDIDATE_DEPTH = 50  # chunks retrieved and cached per question
CANDIDATE_CACHE_VERSION = 1  # raise after a change to parsing, chunking or tokenising code
METRIC_KS = (1, 3, 5, 10)


_FROZEN_CONFIGS = "configs/frozen.txt"


class TestSplitRefused(RuntimeError):
    """A run on the test split was not allowed (ADR-0001)."""

    __test__ = False  # not a pytest test class, despite the name


@dataclass(frozen=True)
class RunResult:
    run_dir: Path
    metrics: dict[str, Any]


@dataclass(frozen=True)
class _Candidates:
    ranking: list[ScoredChunk]  # chunk texts are not cached, so they are empty here
    latency_s: float  # of the original retrieval, also when read from the cache
    cached: bool


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


def _build_retriever(config: Config, root: Path) -> Retriever:
    """Parse and chunk every filing of the dataset, and index the chunks."""
    if config.chunker != "fixed" or config.retriever != "bm25":
        raise NotImplementedError(f"{config.chunker} chunking with {config.retriever} retrieval")
    parser = ParserName(config.parser).make()
    chunker: Chunker = FixedSizeChunker(config.chunk_size, config.chunk_overlap)
    chunks: list[Chunk] = []
    for filing in sorted({q.filing for q in load_questions(root)}):
        chunks += chunker.chunk(filing, parse_filing(parser, root, filing).pages)
    return BM25Retriever(chunks)


def _candidates_dir(config: Config, root: Path) -> Path:
    """One cache folder per combination of the config fields that decide the candidates."""
    key = config.model_dump(
        include={"parser", "chunker", "chunk_size", "chunk_overlap", "retriever", "scope"}
    )
    key |= {"depth": CANDIDATE_DEPTH, "version": CANDIDATE_CACHE_VERSION}
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:12]
    return root / "cache" / "candidates" / digest


def _retrieve_all(config: Config, root: Path, questions: list[Question]) -> list[_Candidates]:
    """The top chunks for every question, from the cache where possible."""
    cache_dir = _candidates_dir(config, root)
    retriever: Retriever | None = None
    results = []
    for question in questions:
        path = cache_dir / f"{question.id}.json"
        if path.exists():
            stored = json.loads(path.read_text(encoding="utf-8"))
            ranking = [
                ScoredChunk(Chunk(text="", **entry["chunk"]), entry["score"])
                for entry in stored["ranking"]
            ]
            results.append(_Candidates(ranking, stored["latency_s"], cached=True))
            continue
        if retriever is None:
            retriever = _build_retriever(config, root)
        start = time.perf_counter()
        ranking = retriever.retrieve(
            question.question,
            filing=question.filing if config.scope == "filing" else None,
            depth=CANDIDATE_DEPTH,
        )
        latency_s = time.perf_counter() - start
        stored = {
            "latency_s": latency_s,
            "ranking": [
                {
                    "chunk": {
                        "id": scored.chunk.id,
                        "filing": scored.chunk.filing,
                        "first_page": scored.chunk.first_page,
                        "last_page": scored.chunk.last_page,
                    },
                    "score": scored.score,
                }
                for scored in ranking
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename, so an interrupted run never leaves a half-written entry.
        part = path.with_name(path.name + ".part")
        part.write_text(json.dumps(stored), encoding="utf-8")
        part.replace(path)
        results.append(_Candidates(ranking, latency_s, cached=False))
    return results


def _question_record(question: Question, candidates: _Candidates) -> dict[str, Any]:
    """One question's page ranking and retrieval metrics. Holds no FinanceBench text."""
    scored_pages = to_page_ranking(candidates.ranking)
    ranking = [page for page, _ in scored_pages]
    evidence: set[PageRef] = {(question.filing, e.page) for e in question.evidence_pages}
    record: dict[str, Any] = {
        "question_id": question.id,
        "filing": question.filing,
        "evidence_pages": sorted(page for _, page in evidence),
        "page_ranking": [[filing, page, score] for (filing, page), score in scored_pages],
        "retrieval_latency_s": candidates.latency_s,
        "candidates_cached": candidates.cached,
        "reciprocal_rank": reciprocal_rank(ranking, evidence),
    }
    for k in METRIC_KS:
        record[f"recall@{k}"] = recall_at_k(ranking, evidence, k)
        record[f"all_evidence_recall@{k}"] = all_evidence_recall_at_k(ranking, evidence, k)
        record[f"ndcg@{k}"] = ndcg_at_k(ranking, evidence, k)
    return record


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [record["retrieval_latency_s"] for record in records]
    metrics: dict[str, Any] = {
        "questions": len(records),
        "mrr": mean(record["reciprocal_rank"] for record in records),
        "retrieval_latency_p50_s": percentile(latencies, 50),
        "retrieval_latency_p95_s": percentile(latencies, 95),
    }
    for k in METRIC_KS:
        for name in (f"recall@{k}", f"all_evidence_recall@{k}", f"ndcg@{k}"):
            metrics[name] = mean(record[name] for record in records)
    return metrics


def _frozen_config_hashes(root: Path) -> set[str]:
    """The committed list of configs that may run on test: one hash per line, `#` for comments."""
    path = root / _FROZEN_CONFIGS
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8").splitlines()
    return {line.split("#")[0].strip() for line in lines} - {""}


def _guard_test_split(config: Config, root: Path, final: bool) -> None:
    if not final:
        raise TestSplitRefused(
            "The test split is only for final reporting. Make every choice on dev, "
            "freeze the config, then pass the final flag."
        )
    if config.config_hash() not in _frozen_config_hashes(root):
        raise TestSplitRefused(
            f"Config '{config.name}' (hash {config.config_hash()}) is not frozen. "
            f"Add its hash to {_FROZEN_CONFIGS} and commit that before the final run."
        )


def run_experiment(
    config: Config, split: Split, runs_root: Path, root: Path, final: bool = False
) -> RunResult:
    """Run one config on one split and write a self-contained run directory.

    Only retrieval exists so far: every run is retrieval-only. A run on the test split needs
    `final` and a frozen config; otherwise it raises `TestSplitRefused` before doing anything.
    """
    if split is Split.TEST:
        _guard_test_split(config, root, final)
    config_hash = config.config_hash()
    # Microsecond timestamps keep run directories unique for back-to-back runs.
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")

    questions = load_split(root, split)
    records = [
        _question_record(question, candidates)
        for question, candidates in zip(
            questions, _retrieve_all(config, root, questions), strict=True
        )
    ]
    metrics = _aggregate(records)

    run_dir = runs_root / f"{stamp}_{config.name}_{split}_{config_hash}"
    run_dir.mkdir(parents=True)
    manifest = {
        "config_hash": config_hash,
        "git_commit": _git_commit(),
        "split": str(split),
        "final": split is Split.TEST,
        "started_at": stamp,
    }
    (run_dir / "config.json").write_text(config.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (run_dir / "questions.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    return RunResult(run_dir=run_dir, metrics=metrics)
