from __future__ import annotations

import pytest

from bachbot.analysis.pipeline import analyze_chorale
from bachbot.analysis.text_music import analyze_text_music
from bachbot.claims.bundle import build_evidence_bundle
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.models.base import TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice


def _make_note(
    *,
    pitch: str | None,
    midi: int | None,
    offset: float,
    measure: int,
    beat: float,
    lyric: str | None = None,
    is_rest: bool = False,
) -> TypedNote:
    return TypedNote(
        pitch=pitch,
        midi=midi,
        duration_quarters=1.0,
        offset_quarters=offset,
        measure_number=measure,
        beat=beat,
        voice_id="S",
        part_name="Soprano",
        lyric=lyric,
        is_rest=is_rest,
        source_ref=f"section_1:m{measure}",
    )


def _text_music_graph() -> EventGraph:
    section = Section(
        section_id="section_1",
        work_id="TEXT-TEST",
        label="Full score",
        section_type="movement",
        measure_start=1,
        measure_end=4,
    )
    voice = Voice(
        voice_id="S",
        section_id=section.section_id,
        part_name="Soprano",
        normalized_voice_name="S",
        instrument_or_role="Soprano",
    )
    notes = [
        _make_note(pitch="C4", midi=60, offset=0.0, measure=1, beat=1.0, lyric="steigen"),
        _make_note(pitch="D4", midi=62, offset=1.0, measure=1, beat=2.0, lyric="und"),
        _make_note(pitch="E4", midi=64, offset=2.0, measure=1, beat=3.0),
        _make_note(pitch="F4", midi=65, offset=3.0, measure=1, beat=4.0),
        _make_note(pitch="G4", midi=67, offset=4.0, measure=2, beat=1.0),
        _make_note(pitch="F4", midi=65, offset=5.0, measure=2, beat=2.0, lyric="fallen"),
        _make_note(pitch="E4", midi=64, offset=6.0, measure=2, beat=3.0),
        _make_note(pitch="D4", midi=62, offset=7.0, measure=2, beat=4.0),
        _make_note(pitch="C4", midi=60, offset=8.0, measure=3, beat=1.0),
        _make_note(pitch="D4", midi=62, offset=9.0, measure=3, beat=2.0, lyric="Tod"),
        _make_note(pitch="C#4", midi=61, offset=10.0, measure=3, beat=3.0),
        _make_note(pitch="C4", midi=60, offset=11.0, measure=3, beat=4.0),
        _make_note(pitch="B3", midi=59, offset=12.0, measure=4, beat=1.0),
        _make_note(pitch=None, midi=None, offset=13.0, measure=4, beat=2.0, is_rest=True),
        _make_note(pitch="A3", midi=57, offset=14.0, measure=4, beat=3.0, lyric="Ach"),
        _make_note(pitch="G3", midi=55, offset=15.0, measure=4, beat=4.0),
    ]
    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id="text-music-fixture",
            work_id="TEXT-TEST",
            source_path="tests/fixtures/chorales/simple_chorale.musicxml",
            title="Text Music Fixture",
            source_format="musicxml",
            meter="4/4",
        ),
        section=section,
        voices=[voice],
        notes=notes,
    )


def _text_music_graph_from_notes(notes: list[TypedNote]) -> EventGraph:
    """Build a minimal EventGraph from a list of TypedNotes (all voice S)."""
    measures = [n.measure_number for n in notes]
    section = Section(
        section_id="section_1",
        work_id="TEXT-TEST",
        label="Full score",
        section_type="movement",
        measure_start=min(measures),
        measure_end=max(measures),
    )
    voice = Voice(
        voice_id="S",
        section_id=section.section_id,
        part_name="Soprano",
        normalized_voice_name="S",
        instrument_or_role="Soprano",
    )
    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id="text-music-fixture",
            work_id="TEXT-TEST",
            source_path="tests/fixtures/chorales/simple_chorale.musicxml",
            title="Text Music Fixture",
            source_format="musicxml",
            meter="4/4",
        ),
        section=section,
        voices=[voice],
        notes=notes,
    )


def test_musicxml_normalization_preserves_lyrics(simple_chorale_graph) -> None:
    lyrics = [note.lyric for note in simple_chorale_graph.notes_by_voice()["S"]]
    assert lyrics == ["Herr", "und", "steigen", "Amen"]


def test_analyze_text_music_detects_prosody_word_painting_and_figures() -> None:
    report = analyze_text_music(_text_music_graph())

    assert report.lyric_voices == ["S"]
    assert report.lyric_event_count == 5
    assert report.prosody.aligned == 3
    assert report.prosody.misaligned == 2

    word_painting = {(item.word, item.figure) for item in report.word_painting}
    assert ("steigen", "anabasis") in word_painting
    assert ("fallen", "catabasis") in word_painting
    assert ("Tod", "passus_duriusculus") in word_painting
    assert ("Ach", "suspiratio") in word_painting

    figures = {item.figure for item in report.rhetorical_figures}
    assert {"anabasis", "catabasis", "passus_duriusculus", "suspiratio"} <= figures


def test_pipeline_and_bundle_include_text_music(simple_chorale_graph) -> None:
    report = analyze_chorale(simple_chorale_graph)
    assert "text_music" in type(report).model_fields
    assert report.text_music["lyric_voices"] == ["S"]
    assert report.text_music["prosody"]["lyric_events"]
    assert any(item["figure"] == "anabasis" for item in report.text_music["rhetorical_figures"])

    bundle = build_evidence_bundle(simple_chorale_graph, report)
    assert "text_music" in bundle.deterministic_findings
    assert bundle.deterministic_findings["text_music"]["lyric_event_count"] == 4


@pytest.mark.parametrize(
    ("description", "notes", "expected_figure", "expected_word"),
    [
        (
            "Anabasis: ascending motion on 'steigen' (cf. BWV 380)",
            [
                _make_note(pitch="C4", midi=60, offset=0.0, measure=1, beat=1.0, lyric="steigen"),
                _make_note(pitch="D4", midi=62, offset=1.0, measure=1, beat=2.0),
                _make_note(pitch="E4", midi=64, offset=2.0, measure=1, beat=3.0),
                _make_note(pitch="F4", midi=65, offset=3.0, measure=1, beat=4.0),
            ],
            "anabasis",
            "steigen",
        ),
        (
            "Catabasis: descending motion on 'fallen' (cf. BWV 4)",
            [
                _make_note(pitch="G4", midi=67, offset=0.0, measure=1, beat=1.0, lyric="fallen"),
                _make_note(pitch="F4", midi=65, offset=1.0, measure=1, beat=2.0),
                _make_note(pitch="E4", midi=64, offset=2.0, measure=1, beat=3.0),
                _make_note(pitch="D4", midi=62, offset=3.0, measure=1, beat=4.0),
            ],
            "catabasis",
            "fallen",
        ),
        (
            "Passus duriusculus: chromatic descent on 'Schmerz' (cf. BWV 78)",
            [
                _make_note(pitch="E4", midi=64, offset=0.0, measure=1, beat=1.0, lyric="Schmerz"),
                _make_note(pitch="Eb4", midi=63, offset=1.0, measure=1, beat=2.0),
                _make_note(pitch="D4", midi=62, offset=2.0, measure=1, beat=3.0),
                _make_note(pitch="Db4", midi=61, offset=3.0, measure=1, beat=4.0),
            ],
            "passus_duriusculus",
            "Schmerz",
        ),
        (
            "Suspiratio: sigh after rest on 'Ach' (cf. BWV 38)",
            [
                _make_note(pitch=None, midi=None, offset=0.0, measure=1, beat=1.0, is_rest=True),
                _make_note(pitch="C4", midi=60, offset=1.0, measure=1, beat=2.0, lyric="Ach"),
                _make_note(pitch="D4", midi=62, offset=2.0, measure=1, beat=3.0),
                _make_note(pitch="E4", midi=64, offset=3.0, measure=1, beat=4.0),
            ],
            "suspiratio",
            "Ach",
        ),
    ],
    ids=["anabasis-BWV380", "catabasis-BWV4", "passus-BWV78", "suspiratio-BWV38"],
)
def test_word_painting_matches_published_rhetorical_figure_examples(
    description: str,
    notes: list[TypedNote],
    expected_figure: str,
    expected_word: str,
) -> None:
    """Validate detection against documented rhetorical figures in Bach scholarship."""
    graph = _text_music_graph_from_notes(notes)
    report = analyze_text_music(graph)

    word_painting_figures = {(item.word, item.figure) for item in report.word_painting}
    assert (expected_word, expected_figure) in word_painting_figures, (
        f"{description}: expected ({expected_word!r}, {expected_figure!r}) "
        f"in {word_painting_figures}"
    )
