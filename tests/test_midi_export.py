"""Tests for MIDI export and round-trip import."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bachbot.exports.midi_export import (
    event_graph_to_midi,
    midi_to_event_graph,
    write_midi,
)

_CORPUS_NORM = Path("data/normalized/dcml_bach_chorales")


def _first_graph_path() -> Path | None:
    paths = sorted(_CORPUS_NORM.glob("*.event_graph.json"))
    return paths[0] if paths else None


# ── Unit tests ────────────────────────────────────────────────────────

def test_midi_export_produces_bytes(simple_chorale_graph) -> None:
    data = event_graph_to_midi(simple_chorale_graph)
    assert isinstance(data, bytes)
    assert len(data) > 0
    # MIDI files start with "MThd"
    assert data[:4] == b"MThd"


def test_midi_export_has_4_tracks(simple_chorale_graph) -> None:
    import mido
    import io

    data = event_graph_to_midi(simple_chorale_graph)
    mid = mido.MidiFile(file=io.BytesIO(data))
    # Must have exactly 4 tracks for SATB
    assert len(mid.tracks) == 4
    # Each track should use a distinct channel (0-3)
    channels = set()
    for track in mid.tracks:
        for msg in track:
            if msg.type == "note_on":
                channels.add(msg.channel)
                break
    assert channels == {0, 1, 2, 3}, f"Expected channels {{0,1,2,3}}, got {channels}"


def test_midi_export_custom_tempo(simple_chorale_graph) -> None:
    import mido
    import io

    data = event_graph_to_midi(simple_chorale_graph, tempo_bpm=60)
    mid = mido.MidiFile(file=io.BytesIO(data))
    # Find tempo message
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                assert msg.tempo == mido.bpm2tempo(60)
                return
    pytest.fail("No set_tempo message found")


def test_write_midi_creates_file(simple_chorale_graph, tmp_path) -> None:
    out = tmp_path / "test.mid"
    write_midi(simple_chorale_graph, out)
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.read_bytes()[:4] == b"MThd"


def test_midi_roundtrip_note_count(simple_chorale_graph, tmp_path) -> None:
    """Export to MIDI, re-import, compare note counts."""
    out = tmp_path / "roundtrip.mid"
    write_midi(simple_chorale_graph, out)
    reimported = midi_to_event_graph(out, work_id="ROUNDTRIP")

    original_pitched = [n for n in simple_chorale_graph.notes if n.midi is not None and not n.is_rest]
    reimported_pitched = [n for n in reimported.notes if n.midi is not None and not n.is_rest]

    # Note count should match exactly
    assert len(reimported_pitched) == len(original_pitched), (
        f"Original: {len(original_pitched)}, Reimported: {len(reimported_pitched)}"
    )


def test_midi_roundtrip_pitch_preservation(simple_chorale_graph, tmp_path) -> None:
    """Export to MIDI, re-import, verify pitches match at each onset+voice."""
    out = tmp_path / "roundtrip.mid"
    write_midi(simple_chorale_graph, out)
    reimported = midi_to_event_graph(out, work_id="ROUNDTRIP")

    # Build (onset, voice) -> midi maps
    from bachbot.benchmark.protocol import VOICE_NORMALIZE

    def _note_map(graph):
        m = {}
        for n in graph.notes:
            if n.midi is None or n.is_rest:
                continue
            role = VOICE_NORMALIZE.get(n.voice_id, n.voice_id)
            m[(round(n.offset_quarters, 2), role)] = n.midi
        return m

    orig = _note_map(simple_chorale_graph)
    reimp = _note_map(reimported)

    mismatches = 0
    for key, midi in orig.items():
        if key in reimp and reimp[key] != midi:
            mismatches += 1
    assert mismatches == 0, f"{mismatches} pitch mismatches in round-trip"


def test_midi_roundtrip_voices(simple_chorale_graph, tmp_path) -> None:
    """Reimported MIDI should have all 4 SATB voices."""
    out = tmp_path / "roundtrip.mid"
    write_midi(simple_chorale_graph, out)
    reimported = midi_to_event_graph(out)
    voice_ids = {n.voice_id for n in reimported.notes}
    assert voice_ids == {"Soprano:1", "Alto:1", "Tenor:1", "Bass:1"}, f"Got voices: {voice_ids}"


# ── Corpus integration tests ─────────────────────────────────────────

@pytest.mark.skipif(not _first_graph_path(), reason="No corpus data")
def test_midi_export_corpus_first_chorale() -> None:
    from bachbot.encodings.event_graph import EventGraph

    gp = _first_graph_path()
    graph = EventGraph.model_validate(json.loads(gp.read_text(encoding="utf-8")))
    data = event_graph_to_midi(graph)
    assert data[:4] == b"MThd"

    import mido
    import io

    mid = mido.MidiFile(file=io.BytesIO(data))
    # Should have 4 tracks for SATB
    assert len(mid.tracks) == 4

    # Total note events should be substantial
    note_count = sum(
        1 for track in mid.tracks for msg in track if msg.type == "note_on" and msg.velocity > 0
    )
    assert note_count > 20


@pytest.mark.skipif(not _first_graph_path(), reason="No corpus data")
def test_midi_roundtrip_corpus() -> None:
    """Full round-trip on a real corpus chorale."""
    import tempfile
    from bachbot.encodings.event_graph import EventGraph

    gp = _first_graph_path()
    graph = EventGraph.model_validate(json.loads(gp.read_text(encoding="utf-8")))

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        midi_path = Path(f.name)

    try:
        write_midi(graph, midi_path)
        reimported = midi_to_event_graph(midi_path, work_id="CORPUS-RT")

        orig_count = len([n for n in graph.notes if n.midi is not None and not n.is_rest])
        reimp_count = len([n for n in reimported.notes if n.midi is not None and not n.is_rest])
        assert reimp_count == orig_count, f"Original: {orig_count}, Reimported: {reimp_count}"
    finally:
        midi_path.unlink(missing_ok=True)
