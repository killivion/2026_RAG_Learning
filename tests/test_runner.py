import json
from pathlib import Path

from typer.testing import CliRunner

from finbench.cli import app
from finbench.config import Config
from finbench.runner import Split, run_experiment

SMOKE = Path(__file__).parents[1] / "configs" / "smoke.yaml"


def test_run_writes_self_contained_run_directory(tmp_path: Path) -> None:
    config = Config(name="smoke", backend="fake")

    result = run_experiment(config, Split.DEV, tmp_path)

    assert result.run_dir.parent == tmp_path
    saved = Config.model_validate_json((result.run_dir / "config.json").read_text())
    assert saved == config
    manifest = json.loads((result.run_dir / "manifest.json").read_text())
    assert manifest["config_hash"] == config.config_hash()
    assert manifest["split"] == "dev"
    assert manifest["git_commit"]
    assert json.loads((result.run_dir / "metrics.json").read_text()) == {}


def test_cli_run_with_smoke_config(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["run", "--config", str(SMOKE), "--runs-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    (run_dir,) = tmp_path.iterdir()
    assert (run_dir / "manifest.json").exists()


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


def test_back_to_back_runs_get_separate_directories(tmp_path: Path) -> None:
    config = Config(name="smoke", backend="fake")

    first = run_experiment(config, Split.DEV, tmp_path)
    second = run_experiment(config, Split.DEV, tmp_path)

    assert first.run_dir != second.run_dir


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
