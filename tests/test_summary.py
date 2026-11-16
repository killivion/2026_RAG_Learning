import csv
from pathlib import Path

from typer.testing import CliRunner

from finbench.cli import app
from finbench.config import Config
from finbench.dataset import Split
from finbench.runner import run_experiment
from finbench.summary import summarize_runs

FILING_SCOPED = Config(name="bm25-filing", scope="filing", chunk_size=10, chunk_overlap=0)
SHARED = Config(name="bm25-shared", scope="shared", chunk_size=10, chunk_overlap=0)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_summary_has_one_row_per_config_with_its_metrics(
    project_root: Path, tmp_path: Path
) -> None:
    runs = tmp_path / "runs"
    shared = run_experiment(SHARED, Split.DEV, runs, project_root)
    filing = run_experiment(FILING_SCOPED, Split.DEV, runs, project_root)

    rows = read_rows(summarize_runs(runs, tmp_path / "results" / "retrieval_runs.csv"))

    assert [row["config"] for row in rows] == ["bm25-filing", "bm25-shared"]
    filing_row, shared_row = rows
    assert filing_row["scope"] == "filing"
    assert filing_row["split"] == "dev"
    assert filing_row["config_hash"] == FILING_SCOPED.config_hash()
    assert filing_row["questions"] == "1"
    assert float(filing_row["recall@5"]) == filing.metrics["recall@5"]
    assert float(filing_row["mrr"]) == filing.metrics["mrr"]
    assert filing_row["run"] == filing.run_dir.name
    assert shared_row["run"] == shared.run_dir.name


def test_summary_keeps_only_the_latest_run_of_a_config(project_root: Path, tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    run_experiment(FILING_SCOPED, Split.DEV, runs, project_root)
    latest = run_experiment(FILING_SCOPED, Split.DEV, runs, project_root)

    rows = read_rows(summarize_runs(runs, tmp_path / "out.csv"))

    assert [row["run"] for row in rows] == [latest.run_dir.name]


def test_summarize_command_writes_the_table(project_root: Path, tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    run_experiment(SHARED, Split.DEV, runs, project_root)
    out = tmp_path / "table.csv"

    result = CliRunner().invoke(app, ["summarize", "--runs-root", str(runs), "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert [row["config"] for row in read_rows(out)] == ["bm25-shared"]
