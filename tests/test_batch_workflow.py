"""Tests for batch enumeration, sync, coverage, and LLM batch analysis."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from typer.testing import CliRunner

from bachbot.cli.main import app
from bachbot.config import get_settings
from bachbot.connectors.bach_digital import BachDigitalConnector
from bachbot.registry.batch import (
    batch_sync_bach_digital,
    build_corpus_coverage_report,
    enumerate_bach_digital_works,
)
from bachbot.registry.catalog import CorpusCatalog


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


def test_enumerate_works_paginates(mock_authority_http) -> None:
    connector = BachDigitalConnector()
    work_ids = enumerate_bach_digital_works(connector, rows_per_page=2, delay=0)
    assert "BachDigitalWork_work_00001262" in work_ids
    assert "BachDigitalWork_work_00009999" in work_ids
    assert len(work_ids) == 2


def test_batch_sync_bach_digital_fetches_all(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "bach_digital")
        catalog = CorpusCatalog()
        connector = BachDigitalConnector()
        summary = batch_sync_bach_digital(
            include_linked=False,
            delay=0,
            dry_run=False,
            rows_per_page=2,
            catalog=catalog,
            connector=connector,
        )
        assert summary["total_works_found"] == 2
        assert summary["synced"] == 2
        assert summary["dry_run"] is False

    records_root = workspace / "data/raw/bach_digital/records/work"
    assert (records_root / "BachDigitalWork_work_00001262" / "record_metadata.json").exists()
    assert (records_root / "BachDigitalWork_work_00009999" / "record_metadata.json").exists()


def test_batch_sync_resumes_skipping_existing(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "bach_digital")
        catalog = CorpusCatalog()
        connector = BachDigitalConnector()

        # First sync: fetch everything
        summary1 = batch_sync_bach_digital(
            include_linked=False, delay=0, dry_run=False,
            rows_per_page=2, catalog=catalog, connector=connector,
        )
        assert summary1["synced"] == 2

        # Second sync: everything already exists, should skip
        summary2 = batch_sync_bach_digital(
            include_linked=False, delay=0, dry_run=False,
            rows_per_page=2, catalog=catalog, connector=connector,
        )
        assert summary2["already_synced"] == 2
        assert summary2["synced"] == 0


def test_batch_sync_dry_run(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "bach_digital")
        catalog = CorpusCatalog()
        connector = BachDigitalConnector()
        summary = batch_sync_bach_digital(
            include_linked=False, delay=0, dry_run=True,
            rows_per_page=2, catalog=catalog, connector=connector,
        )
        assert summary["dry_run"] is True
        assert summary["total_works_found"] == 2
        assert summary["synced"] == 0

    # No records should be fetched
    records_root = workspace / "data/raw/bach_digital/records/work"
    assert not records_root.exists() or not list(records_root.iterdir())


def test_corpus_coverage_report(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "bach_digital")
        catalog = CorpusCatalog()
        connector = BachDigitalConnector()

        batch_sync_bach_digital(
            include_linked=False, delay=0, dry_run=False,
            rows_per_page=2, catalog=catalog, connector=connector,
        )

        report = build_corpus_coverage_report(catalog=catalog)
        assert "bach_digital" in report["datasets"]
        assert report["datasets"]["bach_digital"]["synced"] == 2


def test_batch_sync_cli_dry_run(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "bach_digital")
        result = runner.invoke(
            app,
            ["corpus", "batch-sync", "bach_digital", "--dry-run", "--no-include-linked"],
        )
        assert result.exit_code == 0, result.output
        assert "works found" in result.output
        assert "dry-run" in result.output


def test_coverage_cli(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "bach_digital")
        catalog = CorpusCatalog()
        connector = BachDigitalConnector()
        batch_sync_bach_digital(
            include_linked=False, delay=0, dry_run=False,
            rows_per_page=2, catalog=catalog, connector=connector,
        )
        result = runner.invoke(app, ["corpus", "coverage"])
        assert result.exit_code == 0, result.output
        assert "bach_digital" in result.output
        assert "synced=2" in result.output


def test_pipeline_command_open_corpus(tmp_path: Path, fixture_dir: Path) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create a minimal source root with a musicxml file
    source_root = tmp_path / "source"
    source_root.mkdir()
    chorale_src = fixture_dir / "chorales" / "simple_chorale.musicxml"
    if chorale_src.exists():
        (source_root / "simple_chorale.musicxml").write_bytes(chorale_src.read_bytes())

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "dcml_bach_chorales")
        result = runner.invoke(
            app,
            ["corpus", "pipeline", "dcml_bach_chorales", "--source-root", str(source_root)],
        )
        assert result.exit_code == 0, result.output
        assert "Synced" in result.output
        assert "Normalized" in result.output
        assert "Analyzed" in result.output
