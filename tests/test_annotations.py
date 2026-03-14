from __future__ import annotations

import json

from typer.testing import CliRunner

from bachbot.analysis import analyze_graph
from bachbot.analysis.annotations import (
    bundle_to_annotation_layer,
    compare_annotation_layers,
    load_annotation_layer,
    load_dcml_annotation_layer,
)
from bachbot.claims.bundle import build_evidence_bundle
from bachbot.cli.main import app


def test_bundle_to_annotation_layer_normalizes_findings(simple_chorale_graph) -> None:
    bundle = build_evidence_bundle(simple_chorale_graph, analyze_graph(simple_chorale_graph))
    layer = bundle_to_annotation_layer(bundle)

    assert layer.source.source_type == "bachbot"
    assert layer.source.label == "bachbot"
    assert {item.finding_type for item in layer.findings} == {"harmony", "cadence"}
    harmony_labels = [item.value["roman_numeral"] for item in layer.findings if item.finding_type == "harmony"]
    assert harmony_labels[:4] == ["I", "IV", "V", "I"]


def test_compare_annotation_layers_detects_matches_conflicts_and_extras(simple_chorale_graph, fixture_dir) -> None:
    bundle = build_evidence_bundle(simple_chorale_graph, analyze_graph(simple_chorale_graph))
    left = bundle_to_annotation_layer(bundle)
    right = load_annotation_layer(fixture_dir / "annotations" / "simple_chorale_harmony_diff.json")

    diff = compare_annotation_layers(left, right)

    assert len(diff.matches) == 2
    assert len(diff.conflicts) == 1
    assert len(diff.left_only) == 2
    assert len(diff.right_only) == 1
    assert diff.conflicts[0].finding_type == "harmony"
    assert diff.summary.match_count == 2
    assert diff.summary.conflict_count == 1
    assert diff.summary.left_only_count == 2
    assert diff.summary.right_only_count == 1
    assert diff.summary.overlap_count == 3
    assert diff.summary.agreement_ratio == 0.667
    assert diff.summary.by_finding_type["cadence"].match_count == 1
    assert diff.summary.by_finding_type["harmony"].conflict_count == 1


def test_analyze_compare_cli_outputs_annotation_diff(fixture_dir) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "analyze",
            "compare",
            str(fixture_dir / "chorales" / "simple_chorale.musicxml"),
            "--source",
            "bachbot",
            "--source",
            str(fixture_dir / "annotations" / "simple_chorale_harmony_diff.json"),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["matches"]) == 2
    assert len(payload["conflicts"]) == 1
    assert payload["left_source"]["label"] == "bachbot"
    assert payload["right_source"]["label"] == "fixture-analyst"
    assert payload["summary"]["agreement_ratio"] == 0.667


def test_analyze_compare_cli_can_emit_summary_only(fixture_dir) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "analyze",
            "compare",
            str(fixture_dir / "chorales" / "simple_chorale.musicxml"),
            "--source",
            "bachbot",
            "--source",
            str(fixture_dir / "annotations" / "simple_chorale_harmony_diff.json"),
            "--summary-only",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["match_count"] == 2
    assert payload["conflict_count"] == 1
    assert payload["by_finding_type"]["harmony"]["left_only_count"] == 2


def test_analyze_annotate_cli_exports_annotation_layer(fixture_dir) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "analyze",
            "annotate",
            str(fixture_dir / "chorales" / "simple_chorale.musicxml"),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source"]["label"] == "bachbot"
    assert {item["finding_type"] for item in payload["findings"]} == {"harmony", "cadence"}


def test_analyze_annotate_cli_accepts_bundle_json(simple_chorale_graph, tmp_path) -> None:
    bundle = build_evidence_bundle(simple_chorale_graph, analyze_graph(simple_chorale_graph))
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle.model_dump(mode="json")), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "analyze",
            "annotate",
            str(bundle_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["work_id"] == bundle.work_id
    assert payload["source"]["source_type"] == "bachbot"


def test_analyze_compare_cli_dcml_source_no_bundle_found(fixture_dir) -> None:
    """DCML source errors gracefully when no matching bundle exists for the target."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "analyze",
            "compare",
            str(fixture_dir / "chorales" / "simple_chorale.musicxml"),
            "--source",
            "bachbot",
            "--source",
            "dcml",
        ],
    )

    assert result.exit_code != 0
    assert "No DCML evidence bundle found" in result.output


def test_load_dcml_annotation_layer_with_bundle(simple_chorale_graph, tmp_path) -> None:
    """load_dcml_annotation_layer loads a matching evidence bundle by work_id."""
    bundle = build_evidence_bundle(simple_chorale_graph, analyze_graph(simple_chorale_graph))
    work_id = bundle.work_id

    # Write bundle to a temporary dcml directory
    dcml_dir = tmp_path / "dcml_derived"
    dcml_dir.mkdir()
    bundle_path = dcml_dir / f"{work_id}.evidence_bundle.json"
    bundle_path.write_text(json.dumps(bundle.model_dump(mode="json")), encoding="utf-8")

    layer = load_dcml_annotation_layer(work_id, derived_dir=dcml_dir)

    assert layer.source.source_type == "dcml"
    assert layer.source.label == "dcml"
    assert layer.source.version == "dcml_bach_chorales"
    assert layer.work_id == work_id
    assert any(f.finding_type == "harmony" for f in layer.findings)


def test_load_dcml_annotation_layer_no_match(tmp_path) -> None:
    """load_dcml_annotation_layer raises FileNotFoundError when no bundle matches."""
    import pytest

    dcml_dir = tmp_path / "dcml_empty"
    dcml_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="No DCML evidence bundle found"):
        load_dcml_annotation_layer("nonexistent_work", derived_dir=dcml_dir)


def test_load_dcml_annotation_layer_missing_directory(tmp_path) -> None:
    """load_dcml_annotation_layer raises FileNotFoundError when derived dir is absent."""
    import pytest

    missing_dir = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError, match="DCML derived directory not found"):
        load_dcml_annotation_layer("nonexistent_work", derived_dir=missing_dir)
