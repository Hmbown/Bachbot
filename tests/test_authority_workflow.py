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


def test_bach_digital_explicit_sync_normalize_and_analyze(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "bach_digital")

        sync_result = runner.invoke(
            app,
            ["corpus", "sync", "bach_digital", "--kind", "work", "--record-id", "00001262", "--include-linked"],
        )
        assert sync_result.exit_code == 0, sync_result.output
        assert "Synced 2 authority record(s) for bach_digital" in sync_result.output

        normalize_result = runner.invoke(app, ["corpus", "normalize", "bach_digital"])
        assert normalize_result.exit_code == 0, normalize_result.output
        assert "Normalized 2 authority record(s) with 0 skipped and 0 failure(s)" in normalize_result.output

        analyze_result = runner.invoke(app, ["corpus", "analyze", "bach_digital"])
        assert analyze_result.exit_code == 0, analyze_result.output
        assert "Analyzed 2 authority summary record(s) with 0 failure(s)" in analyze_result.output

    raw_inventory = json.loads((workspace / "data/raw/bach_digital/sync_inventory.json").read_text(encoding="utf-8"))
    assert raw_inventory["record_count"] == 2
    assert {record["kind"] for record in raw_inventory["records"]} == {"work", "source"}

    work_summary_path = workspace / "data/normalized/bach_digital/works/BachDigitalWork_work_00001262.summary.json"
    source_summary_path = workspace / "data/normalized/bach_digital/sources/BachDigitalSource_source_00000863.summary.json"
    work_edges_path = workspace / "data/derived/bach_digital/work_source_edges.json"
    external_ref_index_path = workspace / "data/derived/bach_digital/external_ref_index.json"

    assert work_summary_path.exists()
    assert source_summary_path.exists()
    assert work_edges_path.exists()
    assert external_ref_index_path.exists()

    work_summary = json.loads(work_summary_path.read_text(encoding="utf-8"))
    source_summary = json.loads(source_summary_path.read_text(encoding="utf-8"))
    work_edges = json.loads(work_edges_path.read_text(encoding="utf-8"))
    external_ref_index = json.loads(external_ref_index_path.read_text(encoding="utf-8"))

    assert work_summary["linked_source_ids"] == ["BachDigitalSource_source_00000863"]
    assert any(item["value"] == "BWV 1076" for item in work_summary["catalog_identifiers"])
    assert any(ref["source"] == "rism" and ref["value"] == "467004102" for ref in source_summary["external_refs"])
    assert work_edges["edge_count"] >= 1
    assert any(
        edge["work_id"] == "BachDigitalWork_work_00001262"
        and edge["source_id"] == "BachDigitalSource_source_00000863"
        for edge in work_edges["edges"]
    )
    assert any(ref["source"] == "rism" for ref in external_ref_index["external_refs"])


def test_bach_digital_search_persists_payload_and_dedupes(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "bach_digital")
        sync_result = runner.invoke(
            app,
            ["corpus", "sync", "bach_digital", "--kind", "work", "--query", "canon", "--limit", "2", "--no-include-linked"],
        )
        assert sync_result.exit_code == 0, sync_result.output
        assert "Synced 2 authority record(s) for bach_digital" in sync_result.output

    search_files = sorted((workspace / "data/raw/bach_digital/searches").glob("*.json"))
    assert len(search_files) == 1
    search_payload = json.loads(search_files[0].read_text(encoding="utf-8"))
    assert search_payload["request_params"]["q"] == "canon"
    assert search_payload["raw_record_ids"].count("BachDigitalWork_work_00001262") == 2
    assert search_payload["selected_record_ids"] == [
        "BachDigitalWork_work_00001262",
        "BachDigitalWork_work_00009999",
    ]

    raw_inventory = json.loads((workspace / "data/raw/bach_digital/sync_inventory.json").read_text(encoding="utf-8"))
    assert raw_inventory["record_count"] == 2


def test_bach_digital_fielded_search_persists_request_payload(tmp_path: Path, mock_authority_http) -> None:
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
                "work",
                "--query",
                "BWV 1076",
                "--query-field",
                "musicrepo_work01",
                "--limit",
                "1",
                "--no-include-linked",
            ],
        )
        assert sync_result.exit_code == 0, sync_result.output
        assert "Synced 1 authority record(s) for bach_digital" in sync_result.output

    search_payload = json.loads(next((workspace / "data/raw/bach_digital/searches").glob("*.json")).read_text(encoding="utf-8"))
    assert search_payload["request_params"]["q"] == 'musicrepo_work01:"BWV 1076"'
    assert search_payload["selected_record_ids"] == ["BachDigitalWork_work_00001262"]


def test_rism_explicit_sync_normalize_and_analyze_with_marcxml_fallback(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "rism")

        sync_result = runner.invoke(
            app,
            ["corpus", "sync", "rism", "--mode", "sources", "--record-id", "1001145660", "--record-id", "1001145661"],
        )
        assert sync_result.exit_code == 0, sync_result.output
        assert "Synced 2 authority record(s) for rism" in sync_result.output

        normalize_result = runner.invoke(app, ["corpus", "normalize", "rism"])
        assert normalize_result.exit_code == 0, normalize_result.output
        assert "Normalized 2 authority record(s) with 0 skipped and 0 failure(s)" in normalize_result.output

        analyze_result = runner.invoke(app, ["corpus", "analyze", "rism"])
        assert analyze_result.exit_code == 0, analyze_result.output
        assert "Analyzed 2 authority summary record(s) with 0 failure(s)" in analyze_result.output

    assert (workspace / "data/raw/rism/records/source/1001145660/marcxml.xml").exists()
    marcxml_status = json.loads(
        (workspace / "data/raw/rism/records/source/1001145661/marcxml_status.json").read_text(encoding="utf-8")
    )
    assert marcxml_status["status_code"] == 406

    summary_path = workspace / "data/normalized/rism/sources/1001145660.summary.json"
    relationship_index_path = workspace / "data/derived/rism/relationship_index.json"
    external_resource_index_path = workspace / "data/derived/rism/external_resource_index.json"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    relationship_index = json.loads(relationship_index_path.read_text(encoding="utf-8"))
    external_resource_index = json.loads(external_resource_index_path.read_text(encoding="utf-8"))

    assert summary["standardized_title"] == "Fugues"
    assert any(ref["source"] == "bach_digital" for ref in summary["external_refs"])
    assert relationship_index["relationship_count"] >= 3
    assert any(item["relationship"] == "relators:scr" for item in relationship_index["relationships"])
    assert external_resource_index["external_resource_count"] >= 1
    assert any("bach-digital" in item["url"] for item in external_resource_index["external_resources"])


def test_rism_search_supports_free_text_and_fielded_queries(tmp_path: Path, mock_authority_http) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with workspace_cwd(workspace):
        _register_manifest(runner, repo_root, "rism")

        free_text_result = runner.invoke(
            app,
            ["corpus", "sync", "rism", "--mode", "sources", "--query", "bach", "--limit", "1", "--rows", "20"],
        )
        assert free_text_result.exit_code == 0, free_text_result.output
        assert "Synced 1 authority record(s) for rism" in free_text_result.output

    search_payload = json.loads(next((workspace / "data/raw/rism/searches").glob("*.json")).read_text(encoding="utf-8"))
    assert search_payload["request_params"]["mode"] == "sources"
    assert search_payload["request_params"]["rows"] == "20"
    assert search_payload["selected_record_ids"] == ["1001145660"]

    workspace_fielded = tmp_path / "workspace_fielded"
    workspace_fielded.mkdir()
    with workspace_cwd(workspace_fielded):
        _register_manifest(runner, repo_root, "rism")
        fielded_result = runner.invoke(
            app,
            [
                "corpus",
                "sync",
                "rism",
                "--mode",
                "sources",
                "--query",
                "bach",
                "--query-field",
                "title",
                "--rows",
                "40",
            ],
        )
        assert fielded_result.exit_code == 0, fielded_result.output
        normalize_result = runner.invoke(app, ["corpus", "normalize", "rism"])
        assert normalize_result.exit_code == 0, normalize_result.output

    fielded_search_payload = json.loads(
        next((workspace_fielded / "data/raw/rism/searches").glob("*.json")).read_text(encoding="utf-8")
    )
    assert fielded_search_payload["request_params"]["fq"] == "title:bach"
    assert fielded_search_payload["request_params"]["rows"] == "40"
    assert (workspace_fielded / "data/normalized/rism/sources/1001145660.summary.json").exists()
