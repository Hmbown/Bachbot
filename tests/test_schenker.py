from __future__ import annotations

import json
from pathlib import Path

from bachbot.analysis.pipeline import analyze_chorale
from bachbot.analysis.schenker import analyze_schenkerian
from bachbot.analysis.schenker.prolongation import detect_prolongation_spans
from bachbot.claims.bundle import build_evidence_bundle
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.schenker import StructuralNote


def _note(
    note_id: str,
    voice_id: str,
    onset: float,
    measure: int,
    degree: int,
    midi: int,
    harmony: str = "I",
) -> StructuralNote:
    return StructuralNote(
        note_id=note_id,
        source_note_id=note_id,
        voice_id=voice_id,
        measure=measure,
        onset=onset,
        duration=1.0,
        pitch=None,
        midi=midi,
        scale_degree=degree,
        harmony_label=harmony,
        local_key="C major",
        role="structural",
    )


def test_detect_prolongation_and_zug_spans() -> None:
    notes = [
        _note("n1", "S", 0.0, 1, 5, 79, "I"),
        _note("n2", "S", 1.0, 1, 5, 79, "I"),
        _note("n3", "S", 2.0, 1, 4, 77, "V"),
        _note("n4", "S", 3.0, 1, 3, 76, "V"),
        _note("n5", "S", 4.0, 2, 2, 74, "V"),
    ]
    spans = detect_prolongation_spans(notes, "test")
    span_types = {span.span_type for span in spans}
    assert "prolongation" in span_types
    assert "zug" in span_types


def test_analyze_schenkerian_returns_three_layers(simple_chorale_graph) -> None:
    analysis = analyze_schenkerian(simple_chorale_graph)
    assert analysis.foreground.level == "foreground"
    assert analysis.middleground.level == "middleground"
    assert analysis.background.level == "background"
    assert analysis.foreground.notes
    assert analysis.middleground.notes
    assert analysis.background.notes
    assert all(note.parent_note_id for note in analysis.foreground.notes)
    assert analysis.bassbrechung.detected is True
    assert analysis.bassbrechung.degrees == [1, 5, 1]


def test_pipeline_and_bundle_include_schenkerian(simple_chorale_graph) -> None:
    report = analyze_chorale(simple_chorale_graph)
    assert "schenkerian" in type(report).model_fields
    assert "urlinie" in report.schenkerian
    assert "middleground" in report.schenkerian
    bundle = build_evidence_bundle(simple_chorale_graph, report)
    assert "schenkerian" in bundle.deterministic_findings
    assert bundle.deterministic_findings["schenkerian"]["background"]["notes"]


def test_real_chorale_detects_urlinie() -> None:
    from bachbot.encodings import Normalizer

    graph = Normalizer().normalize("data/raw/dcml_bach_chorales/notes/053 Gelobet seist du, Jesu Christ.notes.tsv")
    analysis = analyze_schenkerian(graph)
    assert analysis.urlinie.detected is True
    assert analysis.urlinie.degrees in ([3, 2, 1], [5, 4, 3, 2, 1], [8, 7, 6, 5, 4, 3, 2, 1])


def test_corpus_urlinie_coverage() -> None:
    base = Path("/Volumes/VIXinSSD/bachbot/data/normalized/dcml_bach_chorales")
    graphs = sorted(base.glob("*.event_graph.json"))
    assert len(graphs) == 361

    detected = 0
    for path in graphs:
        graph = EventGraph(**json.loads(path.read_text()))
        analysis = analyze_schenkerian(graph)
        detected += 1 if analysis.urlinie.detected else 0

    coverage = detected / len(graphs)
    assert coverage >= 0.8, f"Expected Urlinie detection coverage >= 0.8, got {coverage:.3f}"
