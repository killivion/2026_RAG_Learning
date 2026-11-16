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
from finbench.dataset import ChecksumMismatch, Manifest, download, load_questions, summarize
from finbench.llm import (
    CachedBackend,
    ClaudeCodeBackend,
    FakeBackend,
    LLMBackend,
    LLMBackendError,
    LLMRequest,
)
from finbench.runner import Split, run_experiment

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """finbench-rag: retrieval-augmented QA over SEC filings, evaluated on FinanceBench."""


@app.command()
def run(
    config: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Config YAML")],
    split: Annotated[Split, typer.Option(help="Question split")] = Split.DEV,
    runs_root: Annotated[Path, typer.Option(help="Where run directories go")] = Path("runs"),
) -> None:
    """Run one config on one split and write a run directory."""
    try:
        cfg = load_config(config)
    except (ValidationError, yaml.YAMLError) as err:
        typer.echo(f"Invalid config {config}:\n{err}", err=True)
        raise typer.Exit(code=2) from err
    result = run_experiment(cfg, split, runs_root)
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
