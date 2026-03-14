from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from typer.testing import CliRunner

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


def test_local_sync_requires_source_root_and_forbids_remote_options(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    corpus_root = workspace / "seed_corpus"
    corpus_root.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "dcml_bach_chorales")

        missing_source_root = runner.invoke(app, ["corpus", "sync", "dcml_bach_chorales"])
        assert missing_source_root.exit_code != 0
        assert "--source-root is required for dcml_bach_chorales sync" in missing_source_root.output

        forbidden_remote_option = runner.invoke(
            app,
            ["corpus", "sync", "dcml_bach_chorales", "--source-root", str(corpus_root), "--record-id", "123"],
        )
        assert forbidden_remote_option.exit_code != 0
        assert "Remote authority sync options are not supported" in forbidden_remote_option.output


def test_authority_cli_requires_seed_kind_and_mode_and_valid_rows(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "bach_digital")
        _register_manifest(runner, repo_root, "rism")

        missing_bach_kind = runner.invoke(app, ["corpus", "sync", "bach_digital", "--record-id", "00001262"])
        assert missing_bach_kind.exit_code != 0
        assert "--kind work|source is required for bach_digital sync" in missing_bach_kind.output

        missing_authority_seed = runner.invoke(app, ["corpus", "sync", "bach_digital", "--kind", "work"])
        assert missing_authority_seed.exit_code != 0
        assert "Authority sync requires --record-id, --record-url, or --query" in missing_authority_seed.output

        missing_rism_mode = runner.invoke(app, ["corpus", "sync", "rism", "--record-id", "1001145660"])
        assert missing_rism_mode.exit_code != 0
        assert "--mode sources is required for rism sync" in missing_rism_mode.output

        invalid_rows = runner.invoke(
            app,
            ["corpus", "sync", "rism", "--mode", "sources", "--query", "bach", "--rows", "30"],
        )
        assert invalid_rows.exit_code != 0
        assert "--rows must be one of 20, 40, or 100" in invalid_rows.output

        rows_without_query = runner.invoke(
            app,
            ["corpus", "sync", "rism", "--mode", "sources", "--record-id", "1001145660", "--rows", "20"],
        )
        assert rows_without_query.exit_code != 0
        assert "--rows requires --query" in rows_without_query.output

        query_field_without_query = runner.invoke(
            app,
            ["corpus", "sync", "bach_digital", "--kind", "work", "--query-field", "musicrepo_work01", "--record-id", "00001262"],
        )
        assert query_field_without_query.exit_code != 0
        assert "--query-field requires --query" in query_field_without_query.output


def test_duplicate_authority_seeds_collapse_to_one_record(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "bach_digital")
        sync_result = runner.invoke(
            app,
            [
                "corpus",
                "sync",
                "bach_digital",
                "--kind",
                "source",
                "--record-id",
                "00000863",
                "--record-url",
                "https://www.bach-digital.de/receive/BachDigitalSource_source_00000863?lang=en",
                "--no-include-linked",
            ],
        )
        assert sync_result.exit_code == 0, sync_result.output
        assert "Synced 1 authority record(s) for bach_digital" in sync_result.output

    inventory = json.loads((workspace / "data/raw/bach_digital/sync_inventory.json").read_text(encoding="utf-8"))
    assert inventory["record_count"] == 1
    assert inventory["records"][0]["seed_origins"] == ["record-id", "record-url"]
