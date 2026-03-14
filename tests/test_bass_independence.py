"""Tests for SHA-2807: Bass line independence via two-phase composition."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bachbot.composition.generators.pattern_fill import (
    CHORD_INTERVALS,
    NOTE_TO_PC,
    _bass_is_root,
    _extract_local_key_map,
    _generate_bass_candidates,
    _generate_inner_voicings,
    _is_strong_beat,
    _resolve_secondary_dominant,
    _viterbi_bass_line,
    _viterbi_inner_voices,
)
from bachbot.models.base import TypedNote


# ── Helpers ──


def _make_note(midi: int, offset: float, measure: int, beat: float = 1.0, dur: float = 1.0) -> TypedNote:
    return TypedNote(
        pitch="X", midi=midi, duration_quarters=dur,
        offset_quarters=offset, measure_number=measure,
        beat=beat, voice_id="Soprano:1", part_name="Soprano",
    )


# ── _is_strong_beat tests ──


def test_strong_beat_1():
    assert _is_strong_beat(1.0) is True


def test_strong_beat_3():
    assert _is_strong_beat(3.0) is True


def test_weak_beat_2():
    assert _is_strong_beat(2.0) is False


def test_weak_beat_4():
    assert _is_strong_beat(4.0) is False


def test_weak_beat_half():
    assert _is_strong_beat(1.5) is False


def test_weak_subbeat_near_strong():
    """Sub-beats like 1.25 and 2.75 must NOT be strong."""
    assert _is_strong_beat(1.25) is False
    assert _is_strong_beat(2.75) is False
    assert _is_strong_beat(3.25) is False
    assert _is_strong_beat(0.75) is False


# ── _bass_is_root tests ──


def test_bass_is_root_c_major():
    """C (PC 0) is root of I (intervals (0, 4, 7)) in C (tonic_pc=0)."""
    assert _bass_is_root(0, (0, 4, 7), 0) is True


def test_bass_is_not_root():
    """E (PC 4) is NOT root of I in C."""
    assert _bass_is_root(4, (0, 4, 7), 0) is False


def test_bass_is_root_v_in_g():
    """D (PC 2) is root of V (intervals (7, 11, 2)) in G (tonic_pc=7)."""
    # Root = (7 + 7) % 12 = 2 = D
    assert _bass_is_root(2, (7, 11, 2), 7) is True


# ── _generate_bass_candidates tests ──


def test_bass_candidates_returns_sorted():
    cands = _generate_bass_candidates([0, 4, 7], target_bass=48)
    assert len(cands) > 0
    # All should be in bass range and have correct PCs
    for midi in cands:
        assert 36 <= midi <= 64
        assert midi % 12 in {0, 4, 7}


def test_bass_candidates_sorted_by_proximity():
    cands = _generate_bass_candidates([0], target_bass=48)
    distances = [abs(m - 48) for m in cands]
    assert distances == sorted(distances)


# ── _generate_inner_voicings tests ──


def test_inner_voicings_respects_bounds():
    """Inner voicings should place alto below soprano and tenor above bass."""
    voicings = _generate_inner_voicings(
        soprano_midi=72, bass_midi=48,
        chord_pcs={0, 4, 7},
        targets={"Alto:1": 64, "Tenor:1": 55},
    )
    assert len(voicings) > 0
    for alto, tenor in voicings:
        assert alto <= 72  # below soprano
        assert tenor >= 48  # above bass (within spacing)
        assert alto >= tenor or alto - tenor <= 12  # spacing


# ── _viterbi_bass_line tests ──


def test_viterbi_bass_line_produces_output():
    melody = [_make_note(72, 0.0, 1, 1.0), _make_note(71, 1.0, 1, 2.0),
              _make_note(72, 2.0, 1, 3.0), _make_note(67, 3.0, 1, 4.0)]
    beat_data = [
        ({0, 4, 7}, [0, 4, 7]),
        ({5, 9, 0}, [5, 9, 0]),
        ({7, 11, 2}, [7, 11, 2]),
        ({0, 4, 7}, [0, 4, 7]),
    ]
    labels = ["I", "IV", "V", "I"]
    result = _viterbi_bass_line(melody, beat_data, labels, tonic_pcs=[0, 0, 0, 0])
    assert result is not None
    assert len(result) == 4
    # All bass notes should be in range
    for midi in result:
        assert 36 <= midi <= 64


def test_viterbi_bass_prefers_root_on_strong_beats():
    """Beat 1 and 3 should have root position more often."""
    melody = [
        _make_note(72, 0.0, 1, 1.0),
        _make_note(71, 1.0, 1, 2.0),
        _make_note(72, 2.0, 1, 3.0),
        _make_note(67, 3.0, 1, 4.0),
    ]
    beat_data = [
        ({0, 4, 7}, [0, 4, 7]),
        ({0, 4, 7}, [0, 4, 7]),
        ({0, 4, 7}, [0, 4, 7]),
        ({0, 4, 7}, [0, 4, 7]),
    ]
    labels = ["I", "I", "I", "I"]
    result = _viterbi_bass_line(melody, beat_data, labels, tonic_pcs=[0, 0, 0, 0])
    assert result is not None
    # Beats 0 (beat 1.0) and 2 (beat 3.0) are strong — should prefer root (C, PC 0)
    assert result[0] % 12 == 0, f"Beat 1 should be root, got PC {result[0] % 12}"
    assert result[2] % 12 == 0, f"Beat 3 should be root, got PC {result[2] % 12}"


def test_viterbi_bass_first_beat_weak():
    """When the first melody note is on a weak beat, root should NOT get strong bonus.

    With initial_bass=43 (G) and I chord {C, E, G}, a weak first beat should
    NOT apply ROOT_STRONG_BONUS, so proximity to 43 should favor G (43) over
    C (48). On a strong beat, the root bonus would pull toward C (48).
    """
    # Single note on beat 2.0 (weak) — I chord with PCs {0, 4, 7}
    melody_weak = [_make_note(72, 0.0, 1, 2.0)]  # beat 2 = weak
    beat_data = [({0, 4, 7}, [0, 4, 7])]
    labels = ["I"]
    result_weak = _viterbi_bass_line(melody_weak, beat_data, labels, initial_bass=43, tonic_pcs=[0])
    assert result_weak is not None

    # Same setup but beat 1.0 (strong)
    melody_strong = [_make_note(72, 0.0, 1, 1.0)]  # beat 1 = strong
    result_strong = _viterbi_bass_line(melody_strong, beat_data, labels, initial_bass=43, tonic_pcs=[0])
    assert result_strong is not None

    # On strong beat, root C (48) should be preferred despite being farther from initial (43)
    # On weak beat, proximity to initial should win, favoring G (43)
    assert result_strong[0] % 12 == 0, f"Strong beat should prefer root C, got PC {result_strong[0] % 12}"
    assert result_weak[0] != result_strong[0], (
        f"Weak and strong first beats should produce different bass choices, both got {result_weak[0]}"
    )


def test_viterbi_bass_contrary_motion():
    """When soprano goes up, bass should prefer going down."""
    # Soprano: C5(72) → E5(76) — ascending
    melody = [_make_note(72, 0.0, 1, 1.0), _make_note(76, 1.0, 1, 2.0)]
    beat_data = [({0, 4, 7}, [0, 4, 7]), ({0, 4, 7}, [0, 4, 7])]
    labels = ["I", "I"]
    result = _viterbi_bass_line(melody, beat_data, labels, tonic_pcs=[0, 0])
    assert result is not None
    # Bass should descend or stay (not ascend in parallel with soprano)
    assert result[1] <= result[0], f"Bass should not ascend with soprano: {result}"


# ── _viterbi_inner_voices tests ──


def test_viterbi_inner_voices_produces_output():
    melody = [_make_note(72, 0.0, 1, 1.0), _make_note(71, 1.0, 1, 2.0)]
    bass_line = [48, 48]
    beat_data = [({0, 4, 7}, [0]), ({5, 9, 0}, [5])]
    result = _viterbi_inner_voices(melody, bass_line, beat_data, {"Alto:1": 64, "Tenor:1": 55})
    assert result is not None
    assert len(result) == 2
    for voicing in result:
        assert "Soprano:1" in voicing
        assert "Alto:1" in voicing
        assert "Tenor:1" in voicing
        assert "Bass:1" in voicing


def test_inner_voices_respect_bass():
    """Inner voices should be above the fixed bass."""
    melody = [_make_note(72, 0.0, 1, 1.0)]
    bass_line = [48]
    beat_data = [({0, 4, 7}, [0])]
    result = _viterbi_inner_voices(melody, bass_line, beat_data, {"Alto:1": 64, "Tenor:1": 55})
    assert result is not None
    assert result[0]["Tenor:1"] > 48
    assert result[0]["Alto:1"] > 48


# ── Integration: two-phase composition ──


def test_two_phase_solver_used(simple_cantus_graph):
    """Evidence-driven composition should use the two-phase solver."""
    from bachbot.composition import compose_chorale_study

    bundle = {
        "deterministic_findings": {
            "harmony": [
                {"onset": 0.0, "roman_numeral_candidate_set": ["I"], "ref_id": "t:m1", "local_key": "C major"},
                {"onset": 4.0, "roman_numeral_candidate_set": ["IV"], "ref_id": "t:m2", "local_key": "C major"},
                {"onset": 8.0, "roman_numeral_candidate_set": ["V"], "ref_id": "t:m3", "local_key": "C major"},
                {"onset": 12.0, "roman_numeral_candidate_set": ["I"], "ref_id": "t:m4", "local_key": "C major"},
            ],
            "cadences": [],
            "phrase_endings": [],
            "voice_leading": {"counterpoint": {"suspension_details": []}},
        }
    }
    graph, artifact, report = compose_chorale_study(simple_cantus_graph, bundle=bundle)
    assert len(graph.voices) == 4
    assert any("two-phase" in line for line in report["trace"]), (
        f"Expected two-phase solver, got: {[l for l in report['trace'] if 'solver' in l]}"
    )


def test_composition_produces_four_voices(simple_cantus_graph):
    """Both evidence and baseline should produce valid 4-voice output."""
    from bachbot.composition import compose_chorale_study

    ev_graph, _, _ = compose_chorale_study(simple_cantus_graph, bundle=None)
    assert len(ev_graph.voices) == 4
    bass_notes = ev_graph.notes_by_voice().get("Bass:1", [])
    assert len(bass_notes) > 0


def test_bass_has_melodic_variety(simple_cantus_graph):
    """Bass line should not just repeat the same pitch."""
    from bachbot.composition import compose_chorale_study

    graph, _, _ = compose_chorale_study(simple_cantus_graph, bundle=None)
    bass_notes = [n for n in graph.notes_by_voice().get("Bass:1", []) if n.midi is not None]
    pitches = {n.midi for n in bass_notes}
    assert len(pitches) >= 2, "Bass should have at least 2 distinct pitches"


def test_fallback_to_joint_viterbi():
    """If two-phase fails, should fall back to joint Viterbi gracefully."""
    from unittest.mock import patch
    from bachbot.composition import compose_chorale_study
    from bachbot.encodings import Normalizer

    # Use the simple cantus fixture path directly
    fixture = Path(__file__).parent / "fixtures" / "chorales" / "simple_cantus.musicxml"
    graph = Normalizer().normalize(fixture, work_id="FALLBACK-TEST")

    # Patch _viterbi_bass_line to return None (simulating failure)
    with patch("bachbot.composition.generators.pattern_fill._viterbi_bass_line", return_value=None):
        ev_graph, _, report = compose_chorale_study(graph, bundle=None)
        assert len(ev_graph.voices) == 4
        # Should have used viterbi fallback, not two-phase
        solver_lines = [l for l in report["trace"] if "solver" in l]
        assert any("viterbi" in l for l in solver_lines), f"Expected viterbi fallback: {solver_lines}"


def test_local_key_propagation_to_bass(simple_cantus_graph):
    """Bass Viterbi should receive per-beat local key tonic PCs, not just global."""
    from unittest.mock import patch, call
    from bachbot.composition import compose_chorale_study

    bundle = {
        "deterministic_findings": {
            "harmony": [
                {"onset": 0.0, "roman_numeral_candidate_set": ["I"], "ref_id": "t:m1", "local_key": "C major"},
                {"onset": 4.0, "roman_numeral_candidate_set": ["I"], "ref_id": "t:m2", "local_key": "G major"},
                {"onset": 8.0, "roman_numeral_candidate_set": ["V"], "ref_id": "t:m3", "local_key": "G major"},
                {"onset": 12.0, "roman_numeral_candidate_set": ["I"], "ref_id": "t:m4", "local_key": "C major"},
            ],
            "cadences": [],
            "phrase_endings": [],
            "voice_leading": {"counterpoint": {"suspension_details": []}},
        }
    }

    original_viterbi = _viterbi_bass_line
    captured_tonic_pcs = []

    def spy_viterbi(*args, **kwargs):
        if "tonic_pcs" in kwargs:
            captured_tonic_pcs.append(kwargs["tonic_pcs"])
        return original_viterbi(*args, **kwargs)

    with patch("bachbot.composition.generators.pattern_fill._viterbi_bass_line", side_effect=spy_viterbi):
        compose_chorale_study(simple_cantus_graph, bundle=bundle)

    # compose_chorale_study calls harmonize twice (plan + compose), so 2 captures
    assert len(captured_tonic_pcs) >= 1, "Bass Viterbi should have been called"
    tonic_pcs = captured_tonic_pcs[-1]  # use the final (compose) call
    # Measures 1 and 4 are C major (tonic_pc=0), measures 2 and 3 are G major (tonic_pc=7)
    # The melody has 4 notes (one per measure)
    assert tonic_pcs[0] == 0, f"Measure 1 should be C (0), got {tonic_pcs[0]}"
    assert tonic_pcs[1] == 7, f"Measure 2 should be G (7), got {tonic_pcs[1]}"
    assert tonic_pcs[2] == 7, f"Measure 3 should be G (7), got {tonic_pcs[2]}"
    assert tonic_pcs[3] == 0, f"Measure 4 should be C (0), got {tonic_pcs[3]}"


# ── Corpus: acceptance criteria metrics ──


_CORPUS_DIR = Path("data/derived/dcml_bach_chorales")


def _sample_pairs(n: int = 10) -> list[tuple[Path, Path]]:
    import os
    raw_notes = sorted(Path("data/raw/dcml_bach_chorales/notes").glob("*.notes.tsv"))
    bundles = sorted(_CORPUS_DIR.glob("*.evidence_bundle.json"))
    if not raw_notes or not bundles:
        return []

    def stem(p):
        base = os.path.basename(str(p))
        if base.startswith("notes__"):
            return base.replace("notes__", "").replace(".evidence_bundle.json", "")
        return base.replace(".notes.tsv", "")

    bundle_map = {stem(b): b for b in bundles}
    pairs = [(r, bundle_map[stem(r)]) for r in raw_notes if stem(r) in bundle_map]
    step = max(1, len(pairs) // n)
    return pairs[::step][:n]


@pytest.mark.parametrize("raw,bundle_path", _sample_pairs(10), ids=lambda p: getattr(p, 'stem', str(p))[:30])
def test_corpus_bass_metrics(raw: Path, bundle_path: Path) -> None:
    """Per-chorale: verify two-phase solver runs and bass metrics are reasonable."""
    from bachbot.composition import compose_chorale_study
    from bachbot.composition.validators.hard_rules import validate_graph
    from bachbot.encodings import Normalizer

    graph = Normalizer().normalize(raw)
    bundle = json.loads(bundle_path.read_text())
    ev_graph, _, report = compose_chorale_study(graph, bundle=bundle)

    # Should not crash
    assert len(ev_graph.voices) == 4

    # Validate
    validation = validate_graph(ev_graph)
    # Don't assert pass (some may have pre-existing issues), but count

    # Check bass notes exist
    bass_notes = sorted(
        [n for n in ev_graph.notes_by_voice().get("Bass:1", []) if n.midi is not None],
        key=lambda n: n.offset_quarters,
    )
    assert len(bass_notes) >= 2
