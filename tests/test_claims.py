from __future__ import annotations

from bachbot.analysis import analyze_graph
from bachbot.claims import build_evidence_bundle, render_scholar_markdown


def test_evidence_bundle_contains_addressable_findings(simple_chorale_graph) -> None:
    analysis = analyze_graph(simple_chorale_graph)
    bundle = build_evidence_bundle(simple_chorale_graph, analysis)
    assert bundle.bundle_id == "EB-BWV-TEST-section_1"
    assert len(bundle.passage_refs) == 4
    assert len(bundle.deterministic_findings["cadences"]) >= 1
    assert bundle.metadata.catalog_revision == "BWV3"
    assert bundle.metadata.key == "C major"
    assert bundle.metadata.key_mode == "major"
    assert "validation_report" in bundle.deterministic_findings
    assert "claims" in bundle.deterministic_findings


def test_scholar_report_renders_bundle(simple_chorale_graph) -> None:
    analysis = analyze_graph(simple_chorale_graph)
    bundle = build_evidence_bundle(simple_chorale_graph, analysis)
    report = render_scholar_markdown(bundle)
    assert "# Evidence Bundle" in report
    assert "Deterministic Findings" in report
    assert "Catalog revision" in report
