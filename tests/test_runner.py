import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from finbench.cli import app
from finbench.config import Config
from finbench.dataset import Split
from finbench.runner import TestSplitRefused, run_experiment

SMOKE = Path(__file__).parents[1] / "configs" / "smoke.yaml"
FILING_SCOPED = Config(name="bm25", scope="filing", chunk_size=10, chunk_overlap=0)
SHARED = Config(name="bm25", scope="shared", chunk_size=10, chunk_overlap=0)


def freeze(root: Path, *configs: Config) -> None:
    lines = [f"{config.config_hash()}  # {config.name}\n" for config in configs]
    (root / "configs").mkdir(exist_ok=True)
    (root / "configs" / "frozen.txt").write_text("# frozen configs\n" + "".join(lines))


def read_records(run_dir: Path) -> list[dict[str, object]]:
    lines = (run_dir / "questions.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


def test_run_writes_self_contained_run_directory(project_root: Path, tmp_path: Path) -> None:
    result = run_experiment(FILING_SCOPED, Split.DEV, tmp_path / "runs", project_root)

    assert result.run_dir.parent == tmp_path / "runs"
    saved = Config.model_validate_json((result.run_dir / "config.json").read_text())
    assert saved == FILING_SCOPED
    manifest = json.loads((result.run_dir / "manifest.json").read_text())
    assert manifest["config_hash"] == FILING_SCOPED.config_hash()
    assert manifest["split"] == "dev"
    assert manifest["git_commit"]
    assert json.loads((result.run_dir / "metrics.json").read_text()) == result.metrics


def test_run_ranks_the_evidence_page_first_and_reports_retrieval_metrics(
    project_root: Path, tmp_path: Path
) -> None:
    result = run_experiment(FILING_SCOPED, Split.DEV, tmp_path / "runs", project_root)

    (record,) = read_records(result.run_dir)
    assert record["question_id"] == "fixture_003"
    assert record["evidence_pages"] == [0]
    assert record["page_ranking"][0][:2] == ["GLOBEX_2023Q1_10Q", 0]  # type: ignore[index]
    assert result.metrics["questions"] == 1
    assert result.metrics["mrr"] == 1.0
    for k in (1, 3, 5, 10):
        assert result.metrics[f"recall@{k}"] == 1.0
        assert result.metrics[f"all_evidence_recall@{k}"] == 1.0
        assert result.metrics[f"ndcg@{k}"] == 1.0
    assert result.metrics["retrieval_latency_p50_s"] > 0
    assert result.metrics["retrieval_latency_p95_s"] >= result.metrics["retrieval_latency_p50_s"]


def test_all_evidence_recall_needs_both_evidence_pages(project_root: Path, tmp_path: Path) -> None:
    freeze(project_root, FILING_SCOPED)
    result = run_experiment(FILING_SCOPED, Split.TEST, tmp_path / "runs", project_root, final=True)

    two_pages = next(r for r in read_records(result.run_dir) if r["question_id"] == "fixture_002")
    assert two_pages["evidence_pages"] == [3, 7]
    assert two_pages["recall@1"] == 1.0
    assert two_pages["all_evidence_recall@1"] == 0.0
    assert two_pages["all_evidence_recall@3"] == 1.0


def test_filing_scoped_search_never_ranks_pages_of_other_filings(
    project_root: Path, tmp_path: Path
) -> None:
    freeze(project_root, FILING_SCOPED)
    result = run_experiment(FILING_SCOPED, Split.TEST, tmp_path / "runs", project_root, final=True)

    for record in read_records(result.run_dir):
        filings = {filing for filing, _, _ in record["page_ranking"]}  # type: ignore[attr-defined]
        assert filings == {"ACME_2022_10K"}


def test_shared_index_can_rank_pages_of_other_filings(project_root: Path, tmp_path: Path) -> None:
    freeze(project_root, SHARED)
    result = run_experiment(SHARED, Split.TEST, tmp_path / "runs", project_root, final=True)

    filings = {
        filing
        for record in read_records(result.run_dir)
        for filing, _, _ in record["page_ranking"]  # type: ignore[attr-defined]
    }
    assert filings == {"ACME_2022_10K", "GLOBEX_2023Q1_10Q"}


def test_rerun_reuses_cached_candidates(project_root: Path, tmp_path: Path) -> None:
    first = run_experiment(FILING_SCOPED, Split.DEV, tmp_path / "runs", project_root)
    # Without the filings, a rerun can only succeed from the cache.
    shutil.rmtree(project_root / "pdfs")
    shutil.rmtree(project_root / "cache" / "parsed")

    second = run_experiment(FILING_SCOPED, Split.DEV, tmp_path / "runs", project_root)

    assert first.run_dir != second.run_dir
    (first_record,) = read_records(first.run_dir)
    (second_record,) = read_records(second.run_dir)
    assert first_record["candidates_cached"] is False
    assert second_record["candidates_cached"] is True
    assert second_record["page_ranking"] == first_record["page_ranking"]
    assert second.metrics == first.metrics


def test_other_scope_does_not_reuse_the_cache(project_root: Path, tmp_path: Path) -> None:
    run_experiment(FILING_SCOPED, Split.DEV, tmp_path / "runs", project_root)

    result = run_experiment(SHARED, Split.DEV, tmp_path / "runs", project_root)

    (record,) = read_records(result.run_dir)
    assert record["candidates_cached"] is False


def test_cli_run_with_smoke_config(project_root: Path, tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["run", "--config", str(SMOKE), "--runs-root", str(tmp_path), "--root", str(project_root)],
    )

    assert result.exit_code == 0, result.output
    (run_dir,) = (path for path in tmp_path.iterdir() if path != project_root)
    assert (run_dir / "manifest.json").exists()
    assert "recall@5" in result.output


def test_cli_rejects_invalid_config_readably(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: x\nretriever: bm52\nunknown_key: 1\n")

    result = CliRunner().invoke(
        app, ["run", "--config", str(bad), "--runs-root", str(tmp_path / "runs")]
    )

    assert result.exit_code == 2
    assert "retriever" in result.output
    assert "unknown_key" in result.output
    assert not (tmp_path / "runs").exists()


def test_cli_rejects_malformed_yaml_readably(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: [unclosed\n")

    result = CliRunner().invoke(app, ["run", "--config", str(bad), "--runs-root", str(tmp_path)])

    assert result.exit_code == 2
    assert "Invalid config" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_cli_rejects_unknown_split(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["run", "--config", str(SMOKE), "--split", "train", "--runs-root", str(tmp_path)]
    )

    assert result.exit_code != 0
    assert not any(tmp_path.iterdir())


def test_config_rejects_overlap_as_large_as_the_chunk() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        Config(name="x", chunk_size=50, chunk_overlap=50)


def test_test_split_run_without_the_final_flag_is_refused(
    project_root: Path, tmp_path: Path
) -> None:
    freeze(project_root, FILING_SCOPED)

    with pytest.raises(TestSplitRefused, match="final"):
        run_experiment(FILING_SCOPED, Split.TEST, tmp_path / "runs", project_root)

    assert not (tmp_path / "runs").exists()


def test_final_run_of_an_unfrozen_config_is_refused(project_root: Path, tmp_path: Path) -> None:
    freeze(project_root, SHARED)

    with pytest.raises(TestSplitRefused, match="not frozen"):
        run_experiment(FILING_SCOPED, Split.TEST, tmp_path / "runs", project_root, final=True)

    assert not (tmp_path / "runs").exists()


def test_final_run_of_a_frozen_config_is_recorded_as_final(
    project_root: Path, tmp_path: Path
) -> None:
    freeze(project_root, FILING_SCOPED)

    result = run_experiment(FILING_SCOPED, Split.TEST, tmp_path / "runs", project_root, final=True)

    assert json.loads((result.run_dir / "manifest.json").read_text())["final"] is True
    assert result.metrics["questions"] == 2


def test_dev_run_is_not_recorded_as_final(project_root: Path, tmp_path: Path) -> None:
    result = run_experiment(FILING_SCOPED, Split.DEV, tmp_path / "runs", project_root)

    assert json.loads((result.run_dir / "manifest.json").read_text())["final"] is False


def test_cli_explains_why_a_test_split_run_is_refused(project_root: Path, tmp_path: Path) -> None:
    args = ["run", "--config", str(SMOKE), "--runs-root", str(tmp_path / "runs")]
    args += ["--root", str(project_root), "--split", "test"]

    without_flag = CliRunner().invoke(app, args)
    unfrozen = CliRunner().invoke(app, [*args, "--final"])

    assert without_flag.exit_code == 1
    assert "Refused" in without_flag.output
    assert unfrozen.exit_code == 1
    assert "not frozen" in unfrozen.output
    assert not (tmp_path / "runs").exists()
