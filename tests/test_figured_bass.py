from __future__ import annotations

from pathlib import Path

import pytest

from bachbot.analysis import analyze_graph
from bachbot.analysis.harmony.figured_bass import extract_figured_bass, extract_figured_bass_from_events
from bachbot.encodings import Normalizer
from bachbot.encodings.event_graph import VerticalitySlice
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.harmonic_event import HarmonicEvent

_CORPUS_RAW = Path("data/raw/dcml_bach_chorales/notes")
_MANUAL_CASES = [
    ("001 Aus meines Herzens Grunde.notes.tsv", "001 Aus meines Herzens Grunde:h2:200", "6"),
    ("002 Ich danke dir, lieber Herre.notes.tsv", "002 Ich danke dir, lieber Herre:h3:650", "7"),
    ("003 Ach Gott, vom Himmel sieh darein.notes.tsv", "003 Ach Gott, vom Himmel sieh darein:h2:400", "4/3"),
    ("004 Es ist das Heil uns kommen her.notes.tsv", "004 Es ist das Heil uns kommen her:h2:100", "6"),
    ("005 An Wasserflüssen Babylon.notes.tsv", "005 An Wasserflüssen Babylon:h2:150", "7"),
    ("006 Nun lob, mein Seel, den Herren.notes.tsv", "006 Nun lob, mein Seel, den Herren:h3:600", "4/2"),
    ("008 Freuet euch, ihr Christen alle.notes.tsv", "008 Freuet euch, ihr Christen alle:h2:400", "6/5"),
    ("009 Ermuntre dich, mein schwacher Geist.notes.tsv", "009 Ermuntre dich, mein schwacher Geist:h2:350", "4/2"),
    ("010 Aus tiefer Not schrei ich zu dir.notes.tsv", "010 Aus tiefer Not schrei ich zu dir:h2:650", "4/3"),
    ("012 Puer natus in Bethlehem.notes.tsv", "012 Puer natus in Bethlehem:h3:500", "6/4"),
]


def _make_note(pitch: str, midi: int, voice: str, onset: float = 0.0) -> TypedNote:
    return TypedNote(
        pitch=pitch,
        midi=midi,
        duration_quarters=1.0,
        offset_quarters=onset,
        measure_number=1,
        beat=1.0,
        voice_id=voice,
        part_name=voice,
    )


def _make_slice(note_specs: list[tuple[str, int]]) -> VerticalitySlice:
    return VerticalitySlice(
        onset=0.0,
        duration=1.0,
        measure_number=1,
        active_notes=[_make_note(pitch, midi, f"V{index}:1") for index, (pitch, midi) in enumerate(note_specs)],
    )


def _make_event(candidates: list[str], verticality_class: str = "triad") -> HarmonicEvent:
    return HarmonicEvent(
        harmonic_event_id="test:h1:0",
        ref_id="test:m1",
        onset=0.0,
        duration=1.0,
        verticality_class=verticality_class,
        local_key="C major",
        global_key="C major",
        roman_numeral_candidate_set=candidates,
    )


@pytest.mark.parametrize(
    ("note_specs", "candidates", "verticality_class", "expected"),
    [
        ([("C3", 48), ("E3", 52), ("G3", 55)], ["I"], "triad", ""),
        ([("E3", 52), ("G3", 55), ("C4", 60)], ["I"], "triad", "6"),
        ([("G3", 55), ("C4", 60), ("E4", 64)], ["I"], "triad", "6/4"),
        ([("G3", 55), ("B3", 59), ("D4", 62), ("F4", 65)], ["V7"], "seventh", "7"),
        ([("B3", 59), ("D4", 62), ("F4", 65), ("G4", 67)], ["V7"], "seventh", "6/5"),
        ([("D4", 62), ("F4", 65), ("G4", 67), ("B4", 71)], ["V7"], "seventh", "4/3"),
        ([("F4", 65), ("G4", 67), ("B4", 71), ("D5", 74)], ["V7"], "seventh", "4/2"),
    ],
)
def test_extract_figured_bass_from_events_covers_standard_inversions(
    note_specs: list[tuple[str, int]],
    candidates: list[str],
    verticality_class: str,
    expected: str,
) -> None:
    slice_ = _make_slice(note_specs)
    event = _make_event(candidates, verticality_class=verticality_class)
    line = extract_figured_bass_from_events(
        [slice_],
        [event],
        work_id="test",
        encoding_id="test",
        key=KeyEstimate(tonic="C", mode="major"),
    )
    assert line.events[0].figure_summary == expected
    assert event.figured_bass_like_summary == expected


def test_analysis_pipeline_populates_figured_bass_summary(simple_chorale_graph) -> None:
    report = analyze_graph(simple_chorale_graph)
    assert report.harmony
    assert any(event.figured_bass_like_summary is not None for event in report.harmony)


@pytest.mark.skipif(not _CORPUS_RAW.exists(), reason="No raw chorale corpus available")
def test_extract_figured_bass_returns_line_for_real_chorale() -> None:
    graph = Normalizer().normalize(_CORPUS_RAW / "001 Aus meines Herzens Grunde.notes.tsv")
    line = extract_figured_bass(graph)
    assert line.events
    assert line.events[0].bass_pitch is not None


@pytest.mark.skipif(not _CORPUS_RAW.exists(), reason="No raw chorale corpus available")
@pytest.mark.parametrize(("filename", "event_id", "expected"), _MANUAL_CASES)
def test_manual_figured_bass_cases_from_real_chorales(filename: str, event_id: str, expected: str) -> None:
    graph = Normalizer().normalize(_CORPUS_RAW / filename)
    line = extract_figured_bass(graph)
    figures = {event.harmonic_event_id: event.figure_summary for event in line.events}
    assert figures[event_id] == expected
