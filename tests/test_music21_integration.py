from __future__ import annotations

import pytest

from bachbot.integrations.music21 import key_pitch_class, music21_available


pytestmark = pytest.mark.skipif(not music21_available(), reason="music21 not available")


def test_event_graph_to_music21_produces_score_with_parts(simple_chorale_graph) -> None:
    score = simple_chorale_graph.to_music21()

    parts = list(score.parts)
    assert score.metadata is not None
    assert score.metadata.title == simple_chorale_graph.title
    assert [part.id for part in parts] == simple_chorale_graph.ordered_voice_ids()
    assert [part.partName for part in parts] == ["Soprano", "Alto", "Tenor", "Bass"]
    assert all(list(part.recurse().notesAndRests) for part in parts)


def test_event_graph_to_music21_attaches_analysis_lyrics(simple_chorale_graph) -> None:
    score = simple_chorale_graph.to_music21()

    soprano = list(score.parts)[0]
    lyric_text = [
        lyric.text
        for note in soprano.recurse().notes
        for lyric in note.lyrics
    ]

    assert any(text.startswith("RN:") for text in lyric_text)
    assert any(text.startswith("Cadence:") for text in lyric_text)


def test_music21_roundtrip_preserves_note_identity(simple_chorale_graph) -> None:
    round_tripped = simple_chorale_graph.from_music21(simple_chorale_graph.to_music21())

    original = [
        (
            note.voice_id,
            note.measure_number,
            round(note.offset_quarters, 6),
            round(note.duration_quarters, 6),
            note.pitch,
            note.midi,
            note.is_rest,
            note.source_ref,
        )
        for note in simple_chorale_graph.sorted_events()
    ]
    restored = [
        (
            note.voice_id,
            note.measure_number,
            round(note.offset_quarters, 6),
            round(note.duration_quarters, 6),
            note.pitch,
            note.midi,
            note.is_rest,
            note.source_ref,
        )
        for note in round_tripped.sorted_events()
    ]

    assert round_tripped.metadata.encoding_id == simple_chorale_graph.metadata.encoding_id
    assert round_tripped.metadata.work_id == simple_chorale_graph.work_id
    assert round_tripped.metadata.source_format == simple_chorale_graph.metadata.source_format
    assert round_tripped.ordered_voice_ids() == simple_chorale_graph.ordered_voice_ids()
    assert restored == original


def test_music21_key_analysis_matches_bachbot_key_estimate(simple_chorale_graph) -> None:
    expected = simple_chorale_graph.metadata.key_estimate
    assert expected is not None

    score = simple_chorale_graph.to_music21(include_analysis_lyrics=False)
    music21_key = score.analyze("key")

    assert music21_key.mode == expected.mode
    assert music21_key.tonic.pitchClass == key_pitch_class(expected.tonic)
