"""Summary: run directories into one committed results table (numbers only, no filing text)."""

import csv
import json
from pathlib import Path
from typing import Any

_CONFIG_COLUMNS = ("parser", "chunker", "chunk_size", "chunk_overlap", "retriever", "scope")


def _row(run_dir: Path) -> dict[str, Any]:
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    return {
        "config": config["name"],
        "split": manifest["split"],
        "config_hash": manifest["config_hash"],
        **{column: config[column] for column in _CONFIG_COLUMNS},
        **{name: round(value, 4) for name, value in metrics.items()},
        "run": run_dir.name,
        "git_commit": manifest["git_commit"],
    }


def summarize_runs(runs_root: Path, out: Path) -> Path:
    """Write one row per (config, split): the metrics of its latest run and that run's name.

    Every number reported in the README, a ticket or a learning note should come from this file.
    """
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    # Run directory names start with their timestamp, so sorted order is run order.
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        row = _row(run_dir)
        latest[(row["config_hash"], row["split"])] = row
    rows = sorted(latest.values(), key=lambda row: (row["split"], row["config"]))
    columns = list(dict.fromkeys(column for row in rows for column in row))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, columns, restval="")
        writer.writeheader()
        writer.writerows(rows)
    return out
