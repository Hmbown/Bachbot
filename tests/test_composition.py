from __future__ import annotations

import json
from pathlib import Path

import pytest

from bachbot.composition import compose_chorale_study
from bachbot.composition.generators.pattern_fill import _extract_nt_plan, _extract_suspension_plan, _has_forbidden_parallel, _insert_neighbor_tones, _insert_suspensions
from bachbot.composition.state import CompositionState
from bachbot.composition.validators.hard_rules import validate_graph
from bachbot.encodings.event_graph import EventGraph
from bachbot.encodings.musicxml_io import midi_to_note_name
from bachbot.models.base import ArtifactClass, TypedNote

_CORPUS_DIR = Path("data/normalized/dcml_bach_chorales")


def _note(voice_id: str, midi: int, offset: float, duration: float, *, measure: int = 1, beat: float | None = None) -> TypedNote:
    return TypedNote(
        pitch=midi_to_note_name(midi),
        midi=midi,
        duration_quarters=duration,
        offset_quarters=offset,
        measure_number=measure,
        beat=beat if beat is not None else offset + 1.0,
        voice_id=voice_id,
        part_name=voice_id.split(":", 1)[0],
    )


def _corpus_graphs() -> list[Path]:
    """Return up to 20 evenly-spaced corpus event graph paths for parametrized testing."""
    files = sorted(_CORPUS_DIR.glob("*.event_graph.json"))
    if not files:
        return []
    step = max(1, len(files) // 20)
    return files[::step][:20]


def test_compose_chorale_study_returns_labeled_artifact(simple_cantus_graph) -> None:
    graph, artifact, report = compose_chorale_study(simple_cantus_graph)
    assert artifact.artifact_class == ArtifactClass.CHORALE_STUDY
    assert artifact.parent_work_refs == ["CANTUS-TEST"]
    assert len(graph.voices) == 4
    assert report["plan"]["key"] == "C"


def test_generated_chorale_validates(simple_cantus_graph) -> None:
    graph, artifact, report = compose_chorale_study(simple_cantus_graph)
    validation = validate_graph(graph)
    assert artifact.labels_for_display[0] == "Bachbot chorale study"
    assert validation.passed is True
    assert report["validation"]["subject_type"] == "event_graph"


def test_extract_suspension_plan_maps_bundle_voice_labels() -> None:
    bundle = {
        "deterministic_findings": {
            "voice_leading": {
                "counterpoint": {
                    "suspension_details": [
                        {"voice": "A", "measure": 11, "type": "possible_suspension"},
                        {"voice": "Bass:1", "measure": 12, "type": "possible_suspension"},
                        {"voice": "X", "measure": 99, "type": "possible_suspension"},
                    ]
                }
            }
        }
    }

    assert _extract_suspension_plan(bundle) == {(11, "Alto:1"), (12, "Bass:1")}


def test_insert_suspensions_splits_next_beat_for_planned_inner_voice() -> None:
    notes = [
        _note("Soprano:1", 72, 0.0, 1.0, beat=1.0),
        _note("Alto:1", 67, 0.0, 1.0, beat=1.0),
        _note("Tenor:1", 60, 0.0, 1.0, beat=1.0),
        _note("Bass:1", 48, 0.0, 1.0, beat=1.0),
        _note("Soprano:1", 71, 1.0, 1.0, beat=2.0),
        _note("Alto:1", 65, 1.0, 1.0, beat=2.0),
        _note("Tenor:1", 60, 1.0, 1.0, beat=2.0),
        _note("Bass:1", 55, 1.0, 1.0, beat=2.0),
    ]

    state = CompositionState(notes)
    _insert_suspensions(state, {(1, "Alto:1")})
    alto_notes = sorted(
        [note for note in state.notes if note.voice_id == "Alto:1"],
        key=lambda n: n.offset_quarters,
    )

    assert [(note.offset_quarters, note.duration_quarters, note.midi) for note in alto_notes] == [
        (0.0, 1.0, 67),
        (1.0, 0.5, 67),
        (1.5, 0.5, 65),
    ]
    assert next(note for note in state.notes if note.voice_id == "Tenor:1" and note.offset_quarters == 1.0).midi == 60


def test_composition_state_active_notes_match_event_graph(simple_chorale_graph) -> None:
    """CompositionState.active_notes_at must agree with EventGraph.active_notes_at."""
    graph = simple_chorale_graph
    state = CompositionState(list(graph.notes))

    for onset in graph.iter_onsets():
        eg_set = {(n.voice_id, n.midi) for n in graph.active_notes_at(onset) if n.midi is not None}
        cs_set = {(n.voice_id, n.midi) for n in state.active_notes_at(onset) if n.midi is not None}
        assert eg_set == cs_set, f"Mismatch at onset {onset}: EG={eg_set}, CS={cs_set}"


@pytest.mark.parametrize("graph_path", _corpus_graphs(), ids=lambda p: p.stem[:40])
def test_composition_state_parity_corpus(graph_path: Path) -> None:
    """Parametrized: CompositionState matches EventGraph for corpus chorales."""
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    graph = EventGraph.model_validate(data)
    state = CompositionState(list(graph.notes))

    for onset in graph.iter_onsets():
        eg_set = {(n.voice_id, n.midi) for n in graph.active_notes_at(onset) if n.midi is not None}
        cs_set = {(n.voice_id, n.midi) for n in state.active_notes_at(onset) if n.midi is not None}
        assert eg_set == cs_set, f"{graph_path.stem} mismatch at onset {onset}"


def test_composition_state_add_remove() -> None:
    state = CompositionState()
    n = _note("Alto:1", 64, 0.0, 1.0)
    state.add_note(n)
    assert len(state.notes) == 1
    assert state.active_midi_at(0.0) == {"Alto:1": 64}
    assert state.active_midi_at(1.0) == {}  # past end

    state.remove_note(n)
    assert len(state.notes) == 0


def test_composition_state_replace_note() -> None:
    n1 = _note("Alto:1", 64, 0.0, 1.0)
    state = CompositionState([n1])

    sus = _note("Alto:1", 64, 0.0, 0.5)
    res = _note("Alto:1", 62, 0.5, 0.5)
    state.replace_note(n1, [sus, res])

    assert len(state.notes) == 2
    assert state.active_midi_at(0.0) == {"Alto:1": 64}
    assert state.active_midi_at(0.5) == {"Alto:1": 62}


def test_extract_nt_plan_from_bundle() -> None:
    bundle = {
        "deterministic_findings": {
            "harmony": [
                {"onset": 4.0, "nonharmonic_tone_tags": ["NT:D", "PT:C"]},
                {"onset": 8.0, "nonharmonic_tone_tags": ["SUS:E"]},
                {"onset": 12.0, "nonharmonic_tone_tags": ["NT:F#"]},
            ]
        }
    }
    plan = _extract_nt_plan(bundle)
    assert plan == {(4.0, "D"), (12.0, "F#")}


def test_insert_neighbor_tones_decorates_held_pitch() -> None:
    """Neighbor tone splits a held note: note → NT → next note with same pitch."""
    # Voicings chosen to avoid perfect intervals that would block NTs:
    # S moves up, all others static — alto holds 64 across both beats.
    notes = [
        _note("Soprano:1", 72, 0.0, 1.0, beat=1.0),
        _note("Alto:1", 64, 0.0, 1.0, beat=1.0),
        _note("Tenor:1", 57, 0.0, 1.0, beat=1.0),
        _note("Bass:1", 45, 0.0, 1.0, beat=1.0),
        _note("Soprano:1", 74, 1.0, 1.0, beat=2.0),
        _note("Alto:1", 64, 1.0, 1.0, beat=2.0),
        _note("Tenor:1", 57, 1.0, 1.0, beat=2.0),
        _note("Bass:1", 45, 1.0, 1.0, beat=2.0),
    ]

    state = CompositionState(notes)
    _insert_neighbor_tones(state)

    alto_notes = sorted(
        [n for n in state.notes if n.voice_id == "Alto:1"],
        key=lambda n: n.offset_quarters,
    )
    # Should have 3 notes: shortened original, NT, original at beat 2
    assert len(alto_notes) == 3
    # First note shortened
    assert alto_notes[0].offset_quarters == 0.0
    assert alto_notes[0].duration_quarters == 0.5
    assert alto_notes[0].midi == 64
    # NT note (upper neighbor +1 or +2)
    assert alto_notes[1].offset_quarters == 0.5
    assert alto_notes[1].duration_quarters == 0.5
    assert alto_notes[1].midi in (65, 66)  # upper neighbor
    # Next beat note unchanged
    assert alto_notes[2].offset_quarters == 1.0
    assert alto_notes[2].midi == 64


def test_insert_neighbor_tones_plan_gating() -> None:
    """Empty NT plan should insert nothing; plan with matching onset should insert."""
    notes = [
        _note("Soprano:1", 72, 0.0, 1.0, beat=1.0),
        _note("Alto:1", 64, 0.0, 1.0, beat=1.0),
        _note("Tenor:1", 57, 0.0, 1.0, beat=1.0),
        _note("Bass:1", 45, 0.0, 1.0, beat=1.0),
        _note("Soprano:1", 74, 1.0, 1.0, beat=2.0),
        _note("Alto:1", 64, 1.0, 1.0, beat=2.0),
        _note("Tenor:1", 57, 1.0, 1.0, beat=2.0),
        _note("Bass:1", 45, 1.0, 1.0, beat=2.0),
    ]

    state = CompositionState(notes)
    _insert_neighbor_tones(state, nt_plan=set())
    assert len(state.notes) == 8, "Empty NT plan should insert nothing"

    state2 = CompositionState(list(notes))
    _insert_neighbor_tones(state2, nt_plan={(0.0, "E")})
    assert len(state2.notes) == 9, "NT plan at offset 0.0 should insert 1 NT"


def test_insert_neighbor_tones_blocked_by_spacing() -> None:
    """Trial-and-rollback blocks NT when all directions violate spacing."""
    notes = [
        _note("Soprano:1", 74, 0.0, 1.0, beat=1.0),
        _note("Alto:1", 62, 0.0, 1.0, beat=1.0),
        _note("Tenor:1", 50, 0.0, 1.0, beat=1.0),
        _note("Bass:1", 45, 0.0, 1.0, beat=1.0),
        _note("Soprano:1", 74, 1.0, 1.0, beat=2.0),
        _note("Alto:1", 62, 1.0, 1.0, beat=2.0),
        _note("Tenor:1", 52, 1.0, 1.0, beat=2.0),
        _note("Bass:1", 43, 1.0, 1.0, beat=2.0),
    ]

    state = CompositionState(notes)
    _insert_neighbor_tones(state)
    assert len(state.notes) == 8, "All NTs blocked by spacing, state should be unchanged"
    alto_notes = [n for n in state.notes if n.voice_id == "Alto:1"]
    assert all(n.duration_quarters == 1.0 for n in alto_notes), "Rollback should restore durations"


def _make_nt_test_notes() -> list[TypedNote]:
    """Fresh note list for NT tests — avoids shared-object mutation across test cases."""
    return [
        _note("Soprano:1", 72, 0.0, 1.0, beat=1.0),
        _note("Alto:1", 64, 0.0, 1.0, beat=1.0),
        _note("Tenor:1", 57, 0.0, 1.0, beat=1.0),
        _note("Bass:1", 45, 0.0, 1.0, beat=1.0),
        _note("Soprano:1", 74, 1.0, 1.0, beat=2.0),
        _note("Alto:1", 64, 1.0, 1.0, beat=2.0),
        _note("Tenor:1", 57, 1.0, 1.0, beat=2.0),
        _note("Bass:1", 45, 1.0, 1.0, beat=2.0),
    ]


def test_has_forbidden_parallel_unit() -> None:
    """Direct unit test: _has_forbidden_parallel detects true parallel 5ths/8ves."""
    # Parallel 5ths: Alto 64→65 (+1), Tenor 57→58 (+1), interval stays 7 (P5)
    assert _has_forbidden_parallel(
        {"Alto:1": 64, "Tenor:1": 57},
        {"Alto:1": 65, "Tenor:1": 58},
    ) is True

    # Parallel octaves: Soprano 72→74 (+2), Bass 60→62 (+2), interval stays 0 (P8)
    assert _has_forbidden_parallel(
        {"Soprano:1": 72, "Bass:1": 60},
        {"Soprano:1": 74, "Bass:1": 62},
    ) is True

    # Contrary motion to P5 — NOT parallel (opposite direction)
    assert _has_forbidden_parallel(
        {"Alto:1": 64, "Tenor:1": 57},
        {"Alto:1": 65, "Tenor:1": 56},
    ) is False

    # Same interval, no motion — NOT parallel (both static)
    assert _has_forbidden_parallel(
        {"Alto:1": 64, "Tenor:1": 57},
        {"Alto:1": 64, "Tenor:1": 57},
    ) is False


def test_insert_neighbor_tones_blocked_by_real_parallel() -> None:
    """NT blocked by real _has_forbidden_parallel when prior PT creates sub-beat motion.

    Setup: Alto holds 64, Tenor has a passing tone 57→58 at offset 0.5.
    If Alto NT goes 64→65 at 0.5, both voices move up by 1 semitone from a P5 (7),
    creating true parallel 5ths. The real checker must block this.
    """
    notes = [
        _note("Soprano:1", 72, 0.0, 1.0, beat=1.0),
        _note("Alto:1", 64, 0.0, 1.0, beat=1.0),
        _note("Tenor:1", 57, 0.0, 0.5, beat=1.0),   # shortened by prior PT
        _note("Bass:1", 45, 0.0, 1.0, beat=1.0),
        _note("Tenor:1", 58, 0.5, 0.5, beat=1.5),    # passing tone at sub-beat
        _note("Soprano:1", 74, 1.0, 1.0, beat=2.0),
        _note("Alto:1", 64, 1.0, 1.0, beat=2.0),
        _note("Tenor:1", 59, 1.0, 1.0, beat=2.0),
        _note("Bass:1", 45, 1.0, 1.0, beat=2.0),
    ]

    state = CompositionState(notes)

    # Verify the parallel scenario: at offset 0.0→0.5 transition,
    # Alto is 64, Tenor moves 57→58. If Alto NT were 65 at 0.5,
    # that's Alto 64→65 + Tenor 57→58 = parallel 5ths.
    pre = state.active_midi_at(0.0)
    mid = state.active_midi_at(0.5)
    assert pre["Alto:1"] == 64 and pre["Tenor:1"] == 57
    assert mid["Alto:1"] == 64 and mid["Tenor:1"] == 58  # tenor moved, alto held
    # Simulate what the NT would produce: alto moves to 65 at 0.5
    sim_mid = dict(mid)
    sim_mid["Alto:1"] = 65
    assert _has_forbidden_parallel(pre, sim_mid) is True, "Simulated Alto NT creates parallel 5ths"

    _insert_neighbor_tones(state)

    # Alto NT at step +1 (→65) must have been blocked by the real parallel checker.
    # The function may try step +2 (→66) or -1 (→63) or -2 (→62) instead —
    # those don't create parallel 5ths. Check that no alto note at 0.5 has midi=65.
    alto_at_sub = [n for n in state.notes if n.voice_id == "Alto:1" and n.offset_quarters == 0.5]
    assert all(n.midi != 65 for n in alto_at_sub), "Alto NT at midi=65 must be blocked (parallel 5ths with tenor PT)"


def test_insert_neighbor_tones_skips_when_parallel() -> None:
    """Trial-and-rollback blocks NT when parallel check finds forbidden parallel.

    Neighbor tones (1-2 semitone steps) cannot create parallel perfect intervals
    with held SATB voices because the other voices are static at the sub-beat.
    This test patches _has_forbidden_parallel to simulate a parallel detection
    during the region check, verifying the rollback code path works correctly.
    """
    from unittest.mock import patch

    # With real parallel check, NT is inserted (no parallels possible with 1-2 step)
    state_real = CompositionState(_make_nt_test_notes())
    _insert_neighbor_tones(state_real)
    assert len(state_real.notes) == 9, "NT should be inserted with real parallel check"

    # With patched parallel check that always returns True, NT must be rolled back
    state_patched = CompositionState(_make_nt_test_notes())
    with patch("bachbot.composition.generators.pattern_fill._has_forbidden_parallel", return_value=True):
        _insert_neighbor_tones(state_patched)
    assert len(state_patched.notes) == 8, "NT must be rolled back when parallel detected"
    alto_notes = [n for n in state_patched.notes if n.voice_id == "Alto:1"]
    assert all(n.duration_quarters == 1.0 for n in alto_notes), "Rollback must restore durations"
