from __future__ import annotations

from bachbot.analysis import analyze_graph
from bachbot.analysis.harmony.cadence import detect_cadences


def test_cadence_detector_finds_terminal_cadence(simple_chorale_graph) -> None:
    cadences = detect_cadences(simple_chorale_graph)
    assert len(cadences) >= 1
    terminal = cadences[-1]
    assert terminal.ref_id.endswith("m4")
    assert terminal.bass_formula == "5-1"
    assert terminal.soprano_formula == "7-1"


def test_analysis_pipeline_produces_voiceleading_and_validation(simple_chorale_graph) -> None:
    analysis = analyze_graph(simple_chorale_graph)
    assert analysis.key == "C major"
    assert analysis.voice_leading["similar"] >= 1
    assert analysis.validation_report["passed"] is True
    assert len(analysis.harmonic_events) >= 4
    assert analysis.claims[0].statement.startswith("Detected")
