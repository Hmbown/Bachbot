from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from bachbot.analysis import analyze_graph
from bachbot.integrations.pymusica import (
    ScoreIRUnsupportedError,
    event_graph_to_score_ir,
    pymusica_available,
    score_ir_to_event_graph,
)


pytestmark = pytest.mark.skipif(not pymusica_available(), reason="PyMusica backend not available")


def test_event_graph_to_score_ir_preserves_basic_score_shape(simple_chorale_graph) -> None:
    score = event_graph_to_score_ir(simple_chorale_graph, tempo_bpm=88)

    assert score.title == simple_chorale_graph.title
    assert score.tempo.bpm == 88
    assert str(score.meter) == (simple_chorale_graph.meter or "4/4")
    assert [part.name for part in score.parts] == ["Soprano", "Alto", "Tenor", "Bass"]
    assert len(score.export_voices) == len(simple_chorale_graph.ordered_voice_ids())
    assert score.metadata["bachbot_encoding_id"] == simple_chorale_graph.metadata.encoding_id
    assert score.metadata["bachbot_section_measure_end"] == simple_chorale_graph.section.measure_end


def test_event_graph_to_score_ir_preserves_measure_and_voice_identity(simple_chorale_graph) -> None:
    score = event_graph_to_score_ir(simple_chorale_graph, tempo_bpm=88)

    assert score.metadata["bachbot_source_format"] == simple_chorale_graph.metadata.source_format
    assert score.metadata["bachbot_section_measure_start"] == simple_chorale_graph.section.measure_start
    assert score.metadata["bachbot_section_measure_end"] == simple_chorale_graph.section.measure_end
    assert score.metadata["bachbot_voice_order"] == tuple(simple_chorale_graph.ordered_voice_ids())
    assert score.metadata["bachbot_provenance"] == tuple(simple_chorale_graph.metadata.provenance)
    assert score.metadata["bachbot_measure_map"][0]["measure_number_logical"] == simple_chorale_graph.measures[0].measure_number_logical
    assert score.metadata["bachbot_measure_map"][0]["measure_number_notated"] == simple_chorale_graph.measures[0].measure_number_notated

    soprano = score.export_voices[0]
    assert soprano.instrument == "soprano"
    assert soprano.annotations == ("S", "Soprano")
    assert soprano.metadata["bachbot_voice_id"] == "S"
    assert soprano.metadata["bachbot_normalized_voice_name"] == "S"
    assert soprano.metadata["bachbot_part_name"] == "Soprano"
    assert soprano.metadata["bachbot_instrument_or_role"] == "Soprano"


def test_event_graph_to_score_ir_preserves_note_level_provenance_and_articulations(simple_chorale_graph) -> None:
    graph = simple_chorale_graph.model_copy(deep=True)
    graph.voices[0].staff_id = "staff-1"
    graph.voices[0].range_profile = (60, 81)
    graph.voices[0].clef_profile = "treble"

    soprano_note = next(note for note in graph.notes if note.voice_id == "S" and not note.is_rest)
    soprano_note.articulations = ["staccato", "accent"]
    soprano_note.lyric = "Ky"
    soprano_note.fermata = True
    soprano_note.tie_start = True
    soprano_note.accidental = "#"
    soprano_note.source_ref = "custom:ref"

    score = event_graph_to_score_ir(graph, tempo_bpm=88)
    voice = score.export_voices[0]
    event = voice.events.events[0]

    assert voice.metadata["bachbot_staff_id"] == "staff-1"
    assert voice.metadata["bachbot_range_profile"] == (60, 81)
    assert voice.metadata["bachbot_clef_profile"] == "treble"
    assert event.articulation is not None and event.articulation.value == "staccato"
    assert event.metadata["measure_number"] == "1"
    assert event.metadata["voice_id"] == "S"
    assert event.metadata["bachbot_measure_numbers"] == (1,)
    assert event.metadata["bachbot_source_ref"] == "custom:ref"
    assert event.metadata["bachbot_articulations"] == ("staccato", "accent")
    assert event.metadata["bachbot_lyric"] == "Ky"
    assert event.metadata["bachbot_fermata"] is True
    assert event.metadata["bachbot_tie_start"] is True
    assert event.metadata["bachbot_accidental"] == "#"
    assert event.metadata["bachbot_offset_quarters"] == 0.0
    assert event.metadata["bachbot_duration_quarters"] == 4.0
    assert event.metadata["bachbot_pitch_names"] == ("E4",)
    assert event.metadata["bachbot_measure_number_notated"] == 1
    assert event.metadata["bachbot_measure_number_logical"] == 1
    assert event.metadata["bachbot_measure_onset"] == 0.0
    assert event.metadata["bachbot_measure_duration"] == 4.0


def test_score_ir_to_event_graph_round_trip_preserves_supported_identity(simple_chorale_graph) -> None:
    score = event_graph_to_score_ir(simple_chorale_graph, tempo_bpm=88)
    graph = score_ir_to_event_graph(score)

    original = [
        (
            note.voice_id,
            note.measure_number,
            note.offset_quarters,
            note.duration_quarters,
            note.pitch,
            note.source_ref,
        )
        for note in simple_chorale_graph.sorted_events()
        if not note.is_rest
    ]
    round_tripped = [
        (
            note.voice_id,
            note.measure_number,
            note.offset_quarters,
            note.duration_quarters,
            note.pitch,
            note.source_ref,
        )
        for note in graph.sorted_events()
        if not note.is_rest
    ]

    assert graph.metadata.encoding_id == simple_chorale_graph.metadata.encoding_id
    assert graph.metadata.work_id == simple_chorale_graph.work_id
    assert graph.metadata.source_format == simple_chorale_graph.metadata.source_format
    assert graph.ordered_voice_ids() == simple_chorale_graph.ordered_voice_ids()
    assert graph.section.measure_start == simple_chorale_graph.section.measure_start
    assert graph.section.measure_end == simple_chorale_graph.section.measure_end
    assert round_tripped == original


def test_score_ir_to_event_graph_supports_pymusica_authored_analysis_workflow() -> None:
    graph = score_ir_to_event_graph(_pymusica_authored_score(), work_id="PYMUSICA-AUTHORED", encoding_id="PYMUSICA-AUTHORED")
    report = analyze_graph(graph)

    assert graph.metadata.source_format == "pymusica-scoreir"
    assert graph.ordered_voice_ids() == ["S", "A", "T", "B"]
    assert report.work_id == "PYMUSICA-AUTHORED"
    assert report.encoding_id == "PYMUSICA-AUTHORED"
    assert report.harmony
    assert report.validation_report


def test_score_ir_to_event_graph_rejects_chords() -> None:
    from pymusica_lang.ir.events import EventSequence, MusicEvent
    from pymusica_lang.ir.pitch import Pitch
    from pymusica_lang.ir.rhythm import Duration
    from pymusica_lang.ir.score import ScoreIR, VoiceTrack

    score = ScoreIR.from_voices(
        [
            VoiceTrack(
                name="S",
                instrument="soprano",
                events=EventSequence(
                    (
                        MusicEvent(
                            onset=Fraction(0, 1),
                            duration=Duration(Fraction(4, 1)),
                            pitches=(Pitch(60), Pitch(64)),
                        ),
                    ),
                    name="S",
                ),
            )
        ],
        title="Chord Test",
    )

    with pytest.raises(ScoreIRUnsupportedError, match="chords"):
        score_ir_to_event_graph(score)


def test_score_ir_to_event_graph_rejects_pickups() -> None:
    from pymusica_lang.notation import PickupMeasure, ScoreNotation, attach_score_notation

    score = attach_score_notation(
        _pymusica_authored_score(),
        ScoreNotation(pickup=PickupMeasure(Fraction(1, 1))),
    )

    with pytest.raises(ScoreIRUnsupportedError, match="pickup"):
        score_ir_to_event_graph(score)


def test_musicxml_export_can_use_pymusica_backend(simple_chorale_graph, tmp_path: Path) -> None:
    from bachbot.exports.musicxml_export import write_musicxml

    output = tmp_path / "chorale.musicxml"
    write_musicxml(simple_chorale_graph, output, backend="pymusica")

    text = output.read_text(encoding="utf-8")
    assert output.exists()
    assert "<score-partwise" in text
    assert simple_chorale_graph.title in text
    assert "<part-name>soprano</part-name>" in text


def test_midi_export_can_use_pymusica_backend(simple_chorale_graph) -> None:
    import io

    import mido

    from bachbot.exports.midi_export import event_graph_to_midi

    data = event_graph_to_midi(simple_chorale_graph, backend="pymusica", tempo_bpm=72)
    midi = mido.MidiFile(file=io.BytesIO(data))

    assert data[:4] == b"MThd"
    assert len(midi.tracks) == len(simple_chorale_graph.ordered_voice_ids()) + 1


def _pymusica_authored_score():
    from pymusica_lang.ir.events import EventSequence, MusicEvent
    from pymusica_lang.ir.pitch import Pitch
    from pymusica_lang.ir.rhythm import Duration
    from pymusica_lang.ir.score import Meter, Part, ScoreIR, TempoMark, VoiceTrack

    def _voice(name: str, part_name: str, instrument: str, midis: list[int]) -> VoiceTrack:
        events = tuple(
            MusicEvent(
                onset=Fraction(index * 4, 1),
                duration=Duration(Fraction(4, 1)),
                pitches=(Pitch(midi),),
            )
            for index, midi in enumerate(midis)
        )
        return VoiceTrack(
            name=name,
            instrument=instrument,
            events=EventSequence(events, name=name),
            annotations=(name, part_name),
        )

    parts = (
        Part(name="Soprano", voices=(_voice("S", "Soprano", "soprano", [64, 67, 69, 67]),)),
        Part(name="Alto", voices=(_voice("A", "Alto", "alto", [60, 62, 60, 60]),)),
        Part(name="Tenor", voices=(_voice("T", "Tenor", "tenor", [55, 55, 57, 52]),)),
        Part(name="Bass", voices=(_voice("B", "Bass", "bass", [48, 43, 45, 48]),)),
    )
    return ScoreIR(
        title="PyMusica Authored Chorale",
        tempo=TempoMark(84),
        meter=Meter(4, 4),
        parts=parts,
        composer="PyMusica",
        metadata={
            "bachbot_key_estimate_tonic": "C",
            "bachbot_key_estimate_mode": "major",
            "bachbot_key_estimate_confidence": 0.75,
        },
    )
