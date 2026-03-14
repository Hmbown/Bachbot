from __future__ import annotations

from bachbot.encodings.address_maps import build_measure_map


def test_musicxml_normalization_builds_event_graph(simple_chorale_graph) -> None:
    graph = simple_chorale_graph
    assert graph.work_id == "BWV-TEST"
    assert graph.title == "Simple Chorale"
    assert len(graph.voices) == 4
    assert {voice.voice_id for voice in graph.voices} == {"S", "A", "T", "B"}
    assert len(graph.pitch_events()) == 16


def test_measure_map_and_addressability(simple_chorale_graph) -> None:
    graph = simple_chorale_graph
    measure_map = build_measure_map(graph)
    assert len(measure_map) == 4
    assert measure_map[-1].measure_number_logical == 4
    passage = graph.passage_ref(3, 4)
    assert passage.measure_start == 3
    assert set(passage.voice_ids) == {"S", "A", "T", "B"}
    refs = graph.range_references()
    assert refs[0].ref_id == "section_1:m1"

