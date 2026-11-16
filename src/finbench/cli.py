"""Command line: argument parsing only; logic lives in the modules it calls."""

import json
from dataclasses import asdict
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError

from finbench.config import load_config
from finbench.dataset import (
    ChecksumMismatch,
    Manifest,
    Split,
    SplitExists,
    download,
    load_questions,
    load_split,
    summarize,
    write_split,
)
from finbench.llm import (
    CachedBackend,
    ClaudeCodeBackend,
    FakeBackend,
    LLMBackend,
    LLMBackendError,
    LLMRequest,
)
from finbench.parsing import (
    ParserName,
    check_alignment,
    parse_filing,
    write_parser_comparison,
)
from finbench.runner import TestSplitRefused, run_experiment
from finbench.summary import summarize_runs

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """finbench-rag: retrieval-augmented QA over SEC filings, evaluated on FinanceBench."""


@app.command()
def run(
    config: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Config YAML")],
    split: Annotated[Split, typer.Option(help="Question split")] = Split.DEV,
    runs_root: Annotated[Path, typer.Option(help="Where run directories go")] = Path("runs"),
    root: Annotated[Path, typer.Option(help="Project root holding data/ and pdfs/")] = Path("."),
    final: Annotated[
        bool, typer.Option("--final", help="Allow the test split, for a frozen config only")
    ] = False,
) -> None:
    """Run one config on one split and write a run directory."""
    try:
        cfg = load_config(config)
    except (ValidationError, yaml.YAMLError) as err:
        typer.echo(f"Invalid config {config}:\n{err}", err=True)
        raise typer.Exit(code=2) from err
    try:
        result = run_experiment(cfg, split, runs_root, root, final=final)
    except TestSplitRefused as err:
        typer.echo(f"Refused: {err}", err=True)
        raise typer.Exit(code=1) from err
    for name, value in result.metrics.items():
        typer.echo(f"{name}: {value:.4g}")
    typer.echo(f"Run written to {result.run_dir}")


class BackendName(StrEnum):
    CLAUDE_CODE = "claude-code"
    FAKE = "fake"


@app.command()
def llm_ping(
    model: Annotated[str, typer.Option(help="Model id")] = "claude-haiku-5-5",
    backend: Annotated[BackendName, typer.Option(help="LLM backend")] = BackendName.CLAUDE_CODE,
    cache_dir: Annotated[Path, typer.Option(help="LLM cache directory")] = Path("cache/llm"),
) -> None:
    """Make one cached structured-output call and print the output, tokens and notional cost."""
    inner: LLMBackend = (
        FakeBackend([{"reply": "OK"}]) if backend is BackendName.FAKE else ClaudeCodeBackend()
    )
    request = LLMRequest(
        model=model,
        system_prompt="You are a connectivity check. Reply with the single word OK.",
        user_prompt="ping",
        schema={
            "type": "object",
            "properties": {"reply": {"type": "string"}},
            "required": ["reply"],
            "additionalProperties": False,
        },
        prompt_version="ping-v1",
    )
    try:
        # One cache folder per backend, so a fake answer is never served as a real one.
        response = CachedBackend(inner, cache_dir / backend).complete(request)
    except LLMBackendError as err:
        typer.echo(f"LLM call failed: {err}", err=True)
        raise typer.Exit(code=1) from err
    typer.echo(json.dumps(asdict(response), indent=2))


RootOption = Annotated[Path, typer.Option(help="Project root holding data/ and pdfs/")]


@app.command("download")
def download_command(root: RootOption = Path(".")) -> None:
    """Download the FinanceBench files and filings, checking each against its checksum."""
    try:
        report = download(
            root, Manifest.committed(), on_fetch=lambda path: typer.echo(f"Fetching {path}")
        )
    except ChecksumMismatch as err:
        typer.echo(f"Checksum mismatch: {err}", err=True)
        raise typer.Exit(code=1) from err
    typer.echo(f"Downloaded {report.downloaded} files, skipped {report.skipped} already present")


@app.command()
def data_summary(root: RootOption = Path(".")) -> None:
    """Print the dataset's counts."""
    summary = summarize(load_questions(root))
    typer.echo(f"Questions: {summary.questions}")
    typer.echo(f"Companies: {summary.companies}")
    typer.echo(f"Filings: {summary.filings}")
    typer.echo(f"Question types: {summary.question_types}")
    typer.echo(f"Questions by number of evidence pages: {summary.evidence_page_counts}")


@app.command("split")
def split_command(
    root: RootOption = Path("."),
    force: Annotated[
        bool,
        typer.Option(help="Overwrite the frozen split. A protocol violation (ADR-0001)."),
    ] = False,
) -> None:
    """Make the frozen dev/test split, grouped by company, and print each side's summary."""
    try:
        write_split(root, force=force)
    except SplitExists as err:
        typer.echo(f"{err}. The split is frozen; see docs/adr/0001.", err=True)
        raise typer.Exit(code=1) from err
    for split in Split:
        summary = summarize(load_split(root, split))
        typer.echo(
            f"{split}: {summary.questions} questions, {summary.companies} companies, "
            f"{summary.filings} filings, types {summary.question_types}"
        )


@app.command()
def parse_check(
    parser: Annotated[ParserName, typer.Option(help="Parser to check")] = ParserName.PYMUPDF,
    root: RootOption = Path("."),
    worst: Annotated[int, typer.Option(help="How many of the worst pages to list")] = 10,
) -> None:
    """Parse every filing and report how well its pages match the evidence pages."""
    questions = load_questions(root)
    implementation = parser.make()
    pages = {}
    for filing in sorted({q.filing for q in questions}):
        pages[filing] = parse_filing(implementation, root, filing).pages
    report = check_alignment(questions, pages)
    typer.echo(f"Parser: {parser}, {len(pages)} filings, {len(report.rows)} evidence pages")
    typer.echo(f"Match rate: {report.match_rate:.1%}")
    tables = report.table_pages()
    typer.echo(f"Match rate on {len(tables.rows)} table pages: {tables.match_rate:.1%}")
    typer.echo(f"Zero-indexing confirmed (page n beats n-1 and n+1): {report.zero_index_rate:.1%}")
    typer.echo("Worst pages (evidence text score / full page score / best neighbour score):")
    for row in report.worst(worst):
        typer.echo(
            f"  {row.question_id} {row.filing} page {row.page}: "
            f"{row.text_score:.1f} / {row.page_score:.1f} / {row.neighbor_score:.1f}"
        )


@app.command()
def parse_compare(root: RootOption = Path(".")) -> None:
    """Score every parser against the evidence pages and write the comparison table."""
    path = write_parser_comparison(root)
    typer.echo(path.read_text(encoding="utf-8"))
    typer.echo(f"Written to {path}")


@app.command("summarize")
def summarize_command(
    runs_root: Annotated[Path, typer.Option(help="Where run directories are")] = Path("runs"),
    out: Annotated[Path, typer.Option(help="Results table to write")] = Path(
        "results/retrieval_runs.csv"
    ),
) -> None:
    """Write the committed results table: the latest run of every config and split."""
    path = summarize_runs(runs_root, out)
    typer.echo(path.read_text(encoding="utf-8"))
    typer.echo(f"Written to {path}")


if __name__ == "__main__":
    # `python -m finbench.cli` runs without the finbench.exe launcher (see CLAUDE.md, long jobs).
    app()
