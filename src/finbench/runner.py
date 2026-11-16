"""Experiment runner: the highest test seam. Turns a config and a split into a run directory."""

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from finbench.config import Config


class Split(StrEnum):
    DEV = "dev"
    TEST = "test"


@dataclass(frozen=True)
class RunResult:
    run_dir: Path
    metrics: dict[str, Any]


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


def run_experiment(config: Config, split: Split, runs_root: Path) -> RunResult:
    """Run one config on one split and write a self-contained run directory.

    The pipeline stages are not built yet, so the run is a no-op with empty metrics.
    """
    config_hash = config.config_hash()
    # Microsecond timestamps keep run directories unique for back-to-back runs.
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = runs_root / f"{stamp}_{config.name}_{split}_{config_hash}"
    run_dir.mkdir(parents=True)

    manifest = {
        "config_hash": config_hash,
        "git_commit": _git_commit(),
        "split": str(split),
        "started_at": stamp,
    }
    metrics: dict[str, Any] = {}

    (run_dir / "config.json").write_text(config.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return RunResult(run_dir=run_dir, metrics=metrics)
