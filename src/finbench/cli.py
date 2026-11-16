"""Command line: argument parsing only; logic lives in the modules it calls."""

from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError

from finbench.config import load_config
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
