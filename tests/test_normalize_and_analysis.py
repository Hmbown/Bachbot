from __future__ import annotations

from bachbot.analysis import analyze_graph
from bachbot.claims.bundle import build_evidence_bundle
from bachbot.encodings import Normalizer, build_measure_map
from bachbot.llm.wrappers import build_prompt_request


def test_normalize_musicxml_fixture() -> None:
    graph = Normalizer().normalize("tests/fixtures/chorales/simple_chorale.musicxml", work_id="FIXTURE-TEST")
    assert graph.title == "Simple Chorale"
    assert len(graph.voices) == 4
    assert len(graph.events) == 16
    assert [measure.measure_number_logical for measure in graph.measures] == [1, 2, 3, 4]


def test_address_map_and_chorale_analysis() -> None:
    graph = Normalizer().normalize("tests/fixtures/chorales/simple_chorale.musicxml", work_id="FIXTURE-TEST")
    refs = build_measure_map(graph)
    report = analyze_graph(graph)
    assert len(refs) == 4
    assert len(report.harmonic_events) >= 4
    assert report.cadences
    assert report.cadences[-1].cadence_type in {"PAC", "IAC"}
    assert report.voice_leading["similar"] >= 1


def test_evidence_bundle_prepares_llm_request() -> None:
    graph = Normalizer().normalize("tests/fixtures/chorales/simple_chorale.musicxml", work_id="FIXTURE-TEST")
    report = analyze_graph(graph)
    bundle = build_evidence_bundle(graph, report)
    request = build_prompt_request("scholar", bundle)
    assert bundle.passage_refs
    assert request.mode == "scholar"
    assert "Evidence Bundle" not in request.prompt_text
