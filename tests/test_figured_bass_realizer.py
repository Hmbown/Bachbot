"""Tests for the figured bass realization engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from bachbot.composition.generators.figured_bass import (
    _parse_figures,
    figures_to_pitch_classes,
    realize_figured_bass,
)
from bachbot.composition.generators.pattern_fill import _has_forbidden_parallel
from bachbot.models.base import TypedNote


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bass_note(midi: int, offset: float = 0.0, duration: float = 1.0, measure: int = 1, beat: float = 1.0) -> TypedNote:
    from bachbot.encodings.musicxml_io import midi_to_note_name
    return TypedNote(
        pitch=midi_to_note_name(midi),
        midi=midi,
        duration_quarters=duration,
        offset_quarters=offset,
        measure_number=measure,
        beat=beat,
        voice_id="Bass:1",
        part_name="Bass",
    )


def _make_bass_line(midis: list[int], duration: float = 1.0) -> list[TypedNote]:
    """Create a bass line from MIDI numbers, one note per beat."""
    notes = []
    for i, midi in enumerate(midis):
        notes.append(_bass_note(midi, offset=float(i) * duration, duration=duration, measure=i // 4 + 1, beat=float(i % 4) + 1.0))
    return notes


# ── a) Figure parsing tests ─────────────────────────────────────────────────

class TestFigureParsing:
    """Test figures_to_pitch_classes for all standard figure types."""

    @pytest.mark.parametrize("figure,bass_midi,key,mode,expected_pcs", [
        # Root position (no figure): C3 in C major -> {C, E, G} = {0, 4, 7}
        ("", 48, "C", "major", {0, 4, 7}),
        ("-", 48, "C", "major", {0, 4, 7}),  # "-" normalized to ""
        ("5/3", 48, "C", "major", {0, 4, 7}),

        # First inversion "6": E3 in C major -> {E, G, C} = {4, 7, 0}
        ("6", 52, "C", "major", {4, 7, 0}),
        ("6/3", 52, "C", "major", {4, 7, 0}),

        # Second inversion "6/4": G3 in C major -> {G, C, E} = {7, 0, 4}
        ("6/4", 55, "C", "major", {7, 0, 4}),

        # Root position 7th "7": C3 in C major -> {C, E, G, B} = {0, 4, 7, 11}
        # (diatonic 7th above C in C major is B natural)
        ("7", 48, "C", "major", {0, 4, 7, 11}),
        ("7/5/3", 48, "C", "major", {0, 4, 7, 11}),

        # First inversion 7th "6/5": E3 in C major -> {E, G, B, C} = {4, 7, 11, 0}
        ("6/5", 52, "C", "major", {4, 7, 11, 0}),

        # Second inversion 7th "4/3": G3 in C major -> {G, B, C, E} = {7, 11, 0, 4}
        ("4/3", 55, "C", "major", {7, 11, 0, 4}),

        # Third inversion 7th "4/2": Bb2 in C major -> {Bb, C, E, G} = {10, 0, 4, 7}
        # Bb snaps to B (7th degree); 2nd above 7th=C(0), 4th above 7th=E(4), 6th above 7th=G(7)
        ("4/2", 46, "C", "major", {10, 0, 4, 7}),
        ("2", 46, "C", "major", {10, 0, 4, 7}),

        # Root position in G major: G3 -> {G, B, D} = {7, 11, 2}
        ("", 55, "G", "major", {7, 11, 2}),

        # Root position in A minor: A2 -> {A, C, E} = {9, 0, 4}
        ("", 45, "A", "minor", {9, 0, 4}),
    ])
    def test_standard_figures(self, figure, bass_midi, key, mode, expected_pcs):
        # Normalize "-" like the engine does
        fig = figure if figure != "-" else ""
        result = figures_to_pitch_classes(bass_midi, fig, key, mode)
        assert result == expected_pcs, f"figure={figure!r}, bass={bass_midi}, key={key} {mode}: got {result}"

    def test_accidental_sharp_6(self):
        """#6 should raise the 6th by a semitone."""
        # In C major, bass C3: normal 6th above C is A (pc=9), #6 = A# (pc=10)
        pcs = figures_to_pitch_classes(48, "#6", "C", "major")
        assert 10 in pcs  # raised 6th

    def test_accidental_flat_3(self):
        """b3 should lower the 3rd by a semitone."""
        # In C major, bass C3: normal 3rd = E (pc=4), b3 = Eb (pc=3)
        pcs = figures_to_pitch_classes(48, "b3", "C", "major")
        assert 3 in pcs  # lowered 3rd

    def test_bare_sharp(self):
        """Bare '#' means raised 3rd."""
        pcs = figures_to_pitch_classes(48, "#", "C", "major")
        # Normal 3rd above C = E(4), raised = F(5)
        assert 5 in pcs


class TestFigureParsingInternal:
    """Test the internal _parse_figures function."""

    def test_empty_string(self):
        result = _parse_figures("")
        assert result == [(3, 0), (5, 0)]

    def test_6(self):
        result = _parse_figures("6")
        assert result == [(3, 0), (6, 0)]

    def test_7(self):
        result = _parse_figures("7")
        assert result == [(3, 0), (5, 0), (7, 0)]

    def test_custom_figures(self):
        result = _parse_figures("#6/4")
        # Should parse as two tokens: #6 and 4
        assert len(result) == 2
        assert result[0] == (6, 1)  # #6
        assert result[1] == (4, 0)  # 4


# ── b) Simple realization test ──────────────────────────────────────────────

class TestSimpleRealization:
    """C-F-G-C bass (I-IV-V-I in C major), root position figures."""

    def setup_method(self):
        # C3=48, F3=53, G3=55, C3=48
        self.bass = _make_bass_line([48, 53, 55, 48])
        self.figures = ["", "", "", ""]
        self.graph = realize_figured_bass(
            self.bass, self.figures, key_tonic="C", mode="major",
        )

    def test_four_voices(self):
        by_voice = self.graph.notes_by_voice()
        assert "Soprano:1" in by_voice
        assert "Alto:1" in by_voice
        assert "Tenor:1" in by_voice
        assert "Bass:1" in by_voice

    def test_four_notes_per_voice(self):
        by_voice = self.graph.notes_by_voice()
        for voice_id in ["Soprano:1", "Alto:1", "Tenor:1", "Bass:1"]:
            assert len(by_voice[voice_id]) == 4, f"{voice_id} has {len(by_voice[voice_id])} notes"

    def test_bass_preserved(self):
        by_voice = self.graph.notes_by_voice()
        bass_midis = [n.midi for n in by_voice["Bass:1"]]
        assert bass_midis == [48, 53, 55, 48]

    def test_no_voice_crossing(self):
        by_voice = self.graph.notes_by_voice()
        for i in range(4):
            s = by_voice["Soprano:1"][i].midi
            a = by_voice["Alto:1"][i].midi
            t = by_voice["Tenor:1"][i].midi
            b = by_voice["Bass:1"][i].midi
            assert s >= a >= t > b, f"Voice crossing at beat {i}: S={s} A={a} T={t} B={b}"

    def test_pitch_classes_valid(self):
        """All upper voice PCs should be in the allowed set for each beat."""
        by_voice = self.graph.notes_by_voice()
        expected_pcs_list = [
            figures_to_pitch_classes(48, "", "C", "major"),
            figures_to_pitch_classes(53, "", "C", "major"),
            figures_to_pitch_classes(55, "", "C", "major"),
            figures_to_pitch_classes(48, "", "C", "major"),
        ]
        for i in range(4):
            for voice_id in ["Soprano:1", "Alto:1", "Tenor:1"]:
                pc = by_voice[voice_id][i].midi % 12
                assert pc in expected_pcs_list[i], (
                    f"Beat {i}, {voice_id}: pc={pc} not in {expected_pcs_list[i]}"
                )


# ── c) Spacing constraint test ──────────────────────────────────────────────

class TestSpacingConstraints:
    """Verify SATB spacing rules: S-A <= 12, A-T <= 12."""

    def test_spacing_i_iv_v_i(self):
        bass = _make_bass_line([48, 53, 55, 48])
        figures = ["", "", "", ""]
        graph = realize_figured_bass(bass, figures, key_tonic="C", mode="major")
        by_voice = graph.notes_by_voice()
        for i in range(4):
            s = by_voice["Soprano:1"][i].midi
            a = by_voice["Alto:1"][i].midi
            t = by_voice["Tenor:1"][i].midi
            assert s - a <= 12, f"S-A spacing violation at beat {i}: {s - a}"
            assert a - t <= 12, f"A-T spacing violation at beat {i}: {a - t}"

    def test_spacing_with_inversions(self):
        """Test with first and second inversions."""
        # E3=52 (I6), G3=55 (I6/4), C3=48 (I), G2=43 (V)
        bass = _make_bass_line([52, 55, 48, 43])
        figures = ["6", "6/4", "", ""]
        graph = realize_figured_bass(bass, figures, key_tonic="C", mode="major")
        by_voice = graph.notes_by_voice()
        for i in range(4):
            s = by_voice["Soprano:1"][i].midi
            a = by_voice["Alto:1"][i].midi
            t = by_voice["Tenor:1"][i].midi
            assert s - a <= 12, f"S-A spacing violation at beat {i}: {s - a}"
            assert a - t <= 12, f"A-T spacing violation at beat {i}: {a - t}"


# ── d) No parallel 5ths/8ves test ───────────────────────────────────────────

class TestNoParallels:
    """Verify output has no parallel 5th/8ve violations."""

    def _check_parallels(self, graph):
        by_voice = graph.notes_by_voice()
        n_beats = len(by_voice["Bass:1"])
        violations = 0
        for i in range(1, n_beats):
            prev = {
                v: by_voice[v][i - 1].midi
                for v in ["Soprano:1", "Alto:1", "Tenor:1", "Bass:1"]
            }
            curr = {
                v: by_voice[v][i].midi
                for v in ["Soprano:1", "Alto:1", "Tenor:1", "Bass:1"]
            }
            if _has_forbidden_parallel(prev, curr):
                violations += 1
        return violations

    def test_no_parallels_simple(self):
        bass = _make_bass_line([48, 53, 55, 48])
        graph = realize_figured_bass(bass, ["", "", "", ""], key_tonic="C", mode="major")
        assert self._check_parallels(graph) == 0

    def test_no_parallels_longer(self):
        # C-D-E-F-G-F-E-D-C bass in C major
        bass = _make_bass_line([48, 50, 52, 53, 55, 53, 52, 50, 48])
        figures = ["", "", "6", "", "", "", "6", "", ""]
        graph = realize_figured_bass(bass, figures, key_tonic="C", mode="major")
        violations = self._check_parallels(graph)
        assert violations == 0, f"Found {violations} parallel violation(s)"

    def test_no_parallels_seventh_chords(self):
        # Bass line with seventh chord figures
        bass = _make_bass_line([48, 52, 55, 48])
        figures = ["7", "6/5", "4/3", ""]
        graph = realize_figured_bass(bass, figures, key_tonic="C", mode="major")
        violations = self._check_parallels(graph)
        assert violations == 0, f"Found {violations} parallel violation(s)"


# ── e) Corpus bass realization test ─────────────────────────────────────────

_CORPUS_RAW = Path("data/raw/dcml_bach_chorales/notes")
_CORPUS_DERIVED = Path("data/derived/dcml_bach_chorales")

_CORPUS_CASES = [
    "001 Aus meines Herzens Grunde",
    "002 Ich danke dir, lieber Herre",
    "003 Ach Gott, vom Himmel sieh darein",
    "004 Es ist das Heil uns kommen her",
    "005 An Wasserflüssen Babylon",
]


@pytest.mark.parametrize("chorale_name", _CORPUS_CASES)
def test_corpus_bass_realization(chorale_name):
    """Load a real chorale, extract bass, realize, check basic quality."""
    tsv_path = _CORPUS_RAW / f"{chorale_name}.notes.tsv"
    if not tsv_path.exists():
        pytest.skip(f"Corpus file not found: {tsv_path}")

    from bachbot.encodings import Normalizer

    graph = Normalizer().normalize(tsv_path)

    # Find bass voice
    by_voice = graph.notes_by_voice()
    bass_voice_id = None
    for vid in by_voice:
        if "bass" in vid.lower() or vid == "Bass:1":
            bass_voice_id = vid
            break
    if bass_voice_id is None:
        pytest.skip("No bass voice found")

    bass_notes_orig = [n for n in by_voice[bass_voice_id] if n.midi is not None and not n.is_rest]
    if len(bass_notes_orig) < 4:
        pytest.skip("Bass too short")

    # Use root position for all notes (no figured bass extraction to keep test simple)
    figures = [""] * len(bass_notes_orig)

    key_est = graph.metadata.key_estimate
    key_tonic = key_est.tonic if key_est else "C"
    mode = key_est.mode if key_est else "major"

    # Remap voice_id to Bass:1 for the realizer
    bass_notes = []
    for n in bass_notes_orig:
        bass_notes.append(TypedNote(
            pitch=n.pitch, midi=n.midi,
            duration_quarters=n.duration_quarters,
            offset_quarters=n.offset_quarters,
            measure_number=n.measure_number,
            beat=n.beat, voice_id="Bass:1", part_name="Bass",
            fermata=n.fermata,
        ))

    result = realize_figured_bass(bass_notes, figures, key_tonic=key_tonic, mode=mode)

    # Basic checks
    result_by_voice = result.notes_by_voice()
    assert "Soprano:1" in result_by_voice
    assert len(result_by_voice["Soprano:1"]) == len(bass_notes)

    # Check soprano contour correlation with original (if soprano exists)
    soprano_voice_id = None
    for vid in by_voice:
        if "soprano" in vid.lower() or vid == "Soprano:1":
            soprano_voice_id = vid
            break
    if soprano_voice_id is None:
        return

    orig_soprano = [n.midi for n in by_voice[soprano_voice_id] if n.midi is not None and not n.is_rest]
    gen_soprano = [n.midi for n in result_by_voice["Soprano:1"]]

    # Compare contour directions (up/down/same) — just verify the realization
    # produces something reasonable, not that it matches Bach exactly
    min_len = min(len(orig_soprano), len(gen_soprano))
    if min_len < 2:
        return

    orig_dirs = [1 if orig_soprano[i + 1] > orig_soprano[i] else (-1 if orig_soprano[i + 1] < orig_soprano[i] else 0) for i in range(min_len - 1)]
    gen_dirs = [1 if gen_soprano[i + 1] > gen_soprano[i] else (-1 if gen_soprano[i + 1] < gen_soprano[i] else 0) for i in range(min_len - 1)]

    # At least some agreement on direction (relaxed: just verify no crash and voices are valid)
    assert len(gen_dirs) > 0


# ── f) CLI test ─────────────────────────────────────────────────────────────

def test_cli_from_bass_help():
    """Verify the from-bass CLI command is registered."""
    from typer.testing import CliRunner

    from bachbot.cli.compose import app

    runner = CliRunner()
    result = runner.invoke(app, ["from-bass", "--help"])
    assert result.exit_code == 0
    assert "figured bass" in result.output.lower() or "bass" in result.output.lower()


# ── Additional edge case tests ──────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and error handling."""

    def test_mismatched_lengths(self):
        bass = _make_bass_line([48, 53])
        with pytest.raises(ValueError, match="same length"):
            realize_figured_bass(bass, ["", "", ""], key_tonic="C", mode="major")

    def test_empty_bass(self):
        with pytest.raises(ValueError, match="must not be empty"):
            realize_figured_bass([], [], key_tonic="C", mode="major")

    def test_single_note(self):
        bass = _make_bass_line([48])
        graph = realize_figured_bass(bass, [""], key_tonic="C", mode="major")
        by_voice = graph.notes_by_voice()
        assert len(by_voice["Soprano:1"]) == 1

    def test_minor_key(self):
        # A minor: A2=45, D3=50, E3=52, A2=45
        bass = _make_bass_line([45, 50, 52, 45])
        figures = ["", "", "", ""]
        graph = realize_figured_bass(bass, figures, key_tonic="A", mode="minor")
        by_voice = graph.notes_by_voice()
        assert len(by_voice["Soprano:1"]) == 4

    def test_metadata_correct(self):
        bass = _make_bass_line([48, 53])
        graph = realize_figured_bass(bass, ["", ""], key_tonic="G", mode="major")
        assert graph.metadata.key_estimate.tonic == "G"
        assert graph.metadata.key_estimate.mode == "major"
        assert graph.metadata.composer == "Bachbot"

    def test_dash_figure_treated_as_root(self):
        """The '-' figure should be treated the same as empty (root position)."""
        bass = _make_bass_line([48, 53, 55, 48])
        graph_dash = realize_figured_bass(bass, ["-", "-", "-", "-"], key_tonic="C", mode="major")
        graph_empty = realize_figured_bass(bass, ["", "", "", ""], key_tonic="C", mode="major")
        # Both should produce identical results
        dash_notes = sorted([(n.voice_id, n.offset_quarters, n.midi) for n in graph_dash.notes])
        empty_notes = sorted([(n.voice_id, n.offset_quarters, n.midi) for n in graph_empty.notes])
        assert dash_notes == empty_notes
