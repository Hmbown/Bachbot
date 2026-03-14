from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from typer.testing import CliRunner

from bachbot import __version__
from bachbot.cli.main import app
from bachbot.config import get_settings


@contextmanager
def workspace_cwd(workspace: Path):
    previous_cwd = Path.cwd()
    get_settings.cache_clear()
    try:
        os.chdir(workspace)
        yield
    finally:
        os.chdir(previous_cwd)
        get_settings.cache_clear()


def _register_manifest(runner: CliRunner, repo_root: Path, dataset_id: str) -> None:
    result = runner.invoke(app, ["corpus", "register", str(repo_root / "data" / "manifests" / f"{dataset_id}.yaml")])
    assert result.exit_code == 0, result.output


def test_cli_version_option() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"bachbot {__version__}"


def test_python_module_entrypoint_reports_version() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "bachbot", "--version"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"bachbot {__version__}"


def test_quickstart_example_commands_smoke(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chorale_path = repo_root / "examples/chorales/simple_chorale.musicxml"
    cantus_path = repo_root / "examples/chorales/simple_cantus.musicxml"

    analyze_result = runner.invoke(app, ["analyze", "chorale", str(chorale_path)])
    assert analyze_result.exit_code == 0, analyze_result.output
    analyze_payload = json.loads(analyze_result.output)
    assert analyze_payload["work_id"] == "simple_chorale"

    validate_result = runner.invoke(app, ["validate", "score", str(chorale_path)])
    assert validate_result.exit_code == 0, validate_result.output
    validate_payload = json.loads(validate_result.output)
    assert "validation_id" in validate_payload

    with workspace_cwd(workspace):
        report_output = Path("data/derived/example-report.md")
        report_result = runner.invoke(app, ["export", "report", str(chorale_path), "--output", str(report_output)])
        assert report_result.exit_code == 0, report_result.output
        assert report_output.exists()

        compose_prefix = Path("data/derived/example-chorale")
        compose_result = runner.invoke(app, ["compose", "chorale", str(cantus_path), "--output-prefix", str(compose_prefix)])
        assert compose_result.exit_code == 0, compose_result.output
        assert f"MusicXML: {compose_prefix.with_suffix('.musicxml')}" in compose_result.output
        assert f"Artifact: {compose_prefix.with_suffix('.artifact.json')}" in compose_result.output
        assert f"Report: {compose_prefix.with_suffix('.report.json')}" in compose_result.output
        assert compose_prefix.with_suffix(".musicxml").exists()
        assert compose_prefix.with_suffix(".artifact.json").exists()
        assert compose_prefix.with_suffix(".report.json").exists()


def test_quickstart_local_corpus_workflow_smoke(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    example_root = repo_root / "examples/chorales"

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "dcml_bach_chorales")

        sync_result = runner.invoke(app, ["corpus", "sync", "dcml_bach_chorales", "--source-root", str(example_root)])
        assert sync_result.exit_code == 0, sync_result.output

        normalize_result = runner.invoke(app, ["corpus", "normalize", "dcml_bach_chorales"])
        assert normalize_result.exit_code == 0, normalize_result.output

        analyze_result = runner.invoke(app, ["corpus", "analyze", "dcml_bach_chorales"])
        assert analyze_result.exit_code == 0, analyze_result.output

    assert (workspace / "data/raw/dcml_bach_chorales/sync_inventory.json").exists()
    assert (workspace / "data/normalized/dcml_bach_chorales/normalization_index.json").exists()
    assert (workspace / "data/derived/dcml_bach_chorales/analysis_index.json").exists()


def test_cli_output_paths_support_reproducible_file_workflows(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chorale_path = repo_root / "examples/chorales/simple_chorale.musicxml"

    detective_result = runner.invoke(app, ["detective", "scan", str(chorale_path)])
    assert detective_result.exit_code == 0, detective_result.output
    detective_payload = json.loads(detective_result.output)
    assert detective_payload["work_id"] == "simple_chorale"

    with workspace_cwd(workspace):
        analyze_output = Path("data/derived/analysis-bundle.json")
        analyze_result = runner.invoke(app, ["analyze", "chorale", str(chorale_path), "--output", str(analyze_output)])
        assert analyze_result.exit_code == 0, analyze_result.output
        assert analyze_result.output.strip() == str(analyze_output)
        assert json.loads(analyze_output.read_text(encoding="utf-8"))["work_id"] == "simple_chorale"

        validate_output = Path("data/derived/validation-report.json")
        validate_result = runner.invoke(app, ["validate", "score", str(chorale_path), "--output", str(validate_output)])
        assert validate_result.exit_code == 0, validate_result.output
        assert validate_result.output.strip() == str(validate_output)
        assert "validation_id" in json.loads(validate_output.read_text(encoding="utf-8"))

        detective_output = Path("data/derived/detective-scan.json")
        detective_file_result = runner.invoke(app, ["detective", "scan", str(chorale_path), "--output", str(detective_output)])
        assert detective_file_result.exit_code == 0, detective_file_result.output
        assert detective_file_result.output.strip() == str(detective_output)
        assert json.loads(detective_output.read_text(encoding="utf-8"))["bundle_id"].startswith("EB-")
