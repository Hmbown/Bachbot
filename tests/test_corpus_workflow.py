from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from typer.testing import CliRunner

from bachbot.cli.main import app
from bachbot.config import get_settings


def test_dcml_corpus_workflow_end_to_end(tmp_path: Path) -> None:
    runner = CliRunner()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    corpus_root = workspace / "seed_corpus"
    corpus_root.mkdir()
    shutil.copy2("tests/fixtures/chorales/simple_chorale.musicxml", corpus_root / "simple_chorale.musicxml")
    (corpus_root / "notes.txt").write_text("fixture sidecar", encoding="utf-8")

    get_settings.cache_clear()
    previous_cwd = Path.cwd()
    try:
        os.chdir(workspace)
        register_result = runner.invoke(app, ["corpus", "register", str(Path(previous_cwd) / "data/manifests/dcml_bach_chorales.yaml")])
        assert register_result.exit_code == 0, register_result.output

        list_result = runner.invoke(app, ["corpus", "list"])
        assert list_result.exit_code == 0, list_result.output
        assert "dcml_bach_chorales" in list_result.output

        sync_result = runner.invoke(
            app,
            ["corpus", "sync", "dcml_bach_chorales", "--source-root", str(corpus_root)],
        )
        assert sync_result.exit_code == 0, sync_result.output
        assert "Synced 2 asset(s)" in sync_result.output

        normalize_result = runner.invoke(app, ["corpus", "normalize", "dcml_bach_chorales"])
        assert normalize_result.exit_code == 0, normalize_result.output
        assert "Normalized 1 work(s) with 0 skipped and 0 failure(s)" in normalize_result.output

        analyze_result = runner.invoke(app, ["corpus", "analyze", "dcml_bach_chorales"])
        assert analyze_result.exit_code == 0, analyze_result.output
        assert "Analyzed 1 normalized work(s) with 0 failure(s)" in analyze_result.output
    finally:
        os.chdir(previous_cwd)
        get_settings.cache_clear()

    raw_inventory_path = workspace / "data/raw/dcml_bach_chorales/sync_inventory.json"
    normalization_index_path = workspace / "data/normalized/dcml_bach_chorales/normalization_index.json"
    analysis_index_path = workspace / "data/derived/dcml_bach_chorales/analysis_index.json"

    assert raw_inventory_path.exists()
    assert normalization_index_path.exists()
    assert analysis_index_path.exists()

    raw_inventory = json.loads(raw_inventory_path.read_text(encoding="utf-8"))
    normalization_index = json.loads(normalization_index_path.read_text(encoding="utf-8"))
    analysis_index = json.loads(analysis_index_path.read_text(encoding="utf-8"))

    assert raw_inventory["asset_count"] == 2
    assert raw_inventory["normalizable_count"] == 1
    assert normalization_index["normalized_count"] == 1
    assert analysis_index["analysis_count"] == 1

    normalized_record = normalization_index["normalized"][0]
    analysis_record = analysis_index["analyses"][0]

    event_graph_path = Path(normalized_record["event_graph_path"])
    measure_map_path = Path(normalized_record["measure_map_path"])
    bundle_path = Path(analysis_record["bundle_path"])
    report_path = Path(analysis_record["report_path"])

    assert event_graph_path.exists()
    assert measure_map_path.exists()
    assert bundle_path.exists()
    assert report_path.exists()

    event_graph_payload = json.loads(event_graph_path.read_text(encoding="utf-8"))
    measure_map_payload = json.loads(measure_map_path.read_text(encoding="utf-8"))
    bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    report_text = report_path.read_text(encoding="utf-8")

    assert event_graph_payload["metadata"]["encoding_id"] == "simple_chorale"
    assert event_graph_payload["metadata"]["work_id"] == "simple_chorale"
    assert any("Raw checksum" in item for item in event_graph_payload["metadata"]["provenance"])
    assert len(measure_map_payload["measures"]) == 4
    assert bundle_payload["passage_refs"]
    assert bundle_payload["deterministic_findings"]["cadences"]
    assert "# Evidence Bundle" in report_text
