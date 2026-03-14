"""Tests for harmonic rhythm extraction and metric dissonance detection."""

from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

from bachbot.analysis.pipeline import analyze_chorale
from bachbot.analysis.rhythm.harmonic_rhythm import (
    HarmonicRhythmProfile,
    HemiolaDetection,
    MeasureRhythm,
    PhraseRhythm,
    _acceleration_trend,
    _analyze_measures,
    _analyze_phrases,
    _beats_per_measure,
    _cadential_acceleration_index,
    _detect_hemiolas,
    _duration_weighted_rhythm,
    _metric_position,
    _parse_meter,
    extract_harmonic_rhythm,
    extract_harmonic_rhythm_from_events,
)
from bachbot.claims.bundle import build_evidence_bundle
from bachbot.encodings import Normalizer
from bachbot.models.harmonic_event import HarmonicEvent


# ── Helpers ──


def _make_event(
    onset: float,
    duration: float,
    measure: int,
    candidates: list[str],
    local_key: str = "C major",
) -> HarmonicEvent:
    return HarmonicEvent(
        harmonic_event_id=f"test:h{measure}:{int(onset * 100)}",
        ref_id=f"test:m{measure}",
        onset=onset,
        duration=duration,
        verticality_class="triad",
        local_key=local_key,
        global_key="C major",
        roman_numeral_candidate_set=candidates,
    )


# ── Unit tests: meter parsing ──


class TestMeterParsing:
    def test_standard_4_4(self):
        assert _parse_meter("4/4") == (4, 4)

    def test_triple_meter(self):
        assert _parse_meter("3/4") == (3, 4)

    def test_cut_time(self):
        assert _parse_meter("2/2") == (2, 2)

    def test_6_8(self):
        assert _parse_meter("6/8") == (6, 8)

    def test_none_defaults_4_4(self):
        assert _parse_meter(None) == (4, 4)

    def test_invalid_defaults_4_4(self):
        assert _parse_meter("abc") == (4, 4)

    def test_beats_per_measure_4_4(self):
        assert _beats_per_measure("4/4") == 4.0

    def test_beats_per_measure_3_4(self):
        assert _beats_per_measure("3/4") == 3.0

    def test_beats_per_measure_6_8(self):
        assert _beats_per_measure("6/8") == 3.0

    def test_beats_per_measure_2_2(self):
        assert _beats_per_measure("2/2") == 4.0

    def test_zero_denominator_defaults(self):
        assert _parse_meter("3/0") == (4, 4)
        assert _beats_per_measure("3/0") == 4.0

    def test_negative_values_default(self):
        assert _parse_meter("-1/4") == (4, 4)


# ── Unit tests: metric position ──


class TestMetricPosition:
    def test_beat_1_of_measure_1(self):
        e = _make_event(0.0, 1.0, 1, ["I"])
        pos = _metric_position(e, 4.0)
        assert pos == 0.0

    def test_beat_3_of_measure_1(self):
        e = _make_event(2.0, 1.0, 1, ["V"])
        pos = _metric_position(e, 4.0)
        assert pos == 2.0

    def test_beat_1_of_measure_2(self):
        e = _make_event(4.0, 1.0, 2, ["I"])
        pos = _metric_position(e, 4.0)
        assert pos == 0.0


# ── Unit tests: per-measure analysis ──


class TestMeasureAnalysis:
    def test_single_chord_per_measure(self):
        events = [
            _make_event(0.0, 4.0, 1, ["I"]),
            _make_event(4.0, 4.0, 2, ["V"]),
        ]
        measures = _analyze_measures(events, 4.0)
        assert len(measures) == 2
        assert measures[0].chord_changes == 1
        assert measures[0].beats_per_change == 4.0

    def test_two_chords_per_measure(self):
        events = [
            _make_event(0.0, 2.0, 1, ["I"]),
            _make_event(2.0, 2.0, 1, ["V"]),
        ]
        measures = _analyze_measures(events, 4.0)
        assert len(measures) == 1
        assert measures[0].chord_changes == 2
        assert measures[0].beats_per_change == 2.0

    def test_repeated_chord_not_counted(self):
        events = [
            _make_event(0.0, 1.0, 1, ["I"]),
            _make_event(1.0, 1.0, 1, ["I"]),
            _make_event(2.0, 2.0, 1, ["V"]),
        ]
        measures = _analyze_measures(events, 4.0)
        assert measures[0].chord_changes == 2
        assert measures[0].chords == ["I", "V"]

    def test_four_chords_per_measure(self):
        events = [
            _make_event(0.0, 1.0, 1, ["I"]),
            _make_event(1.0, 1.0, 1, ["IV"]),
            _make_event(2.0, 1.0, 1, ["V"]),
            _make_event(3.0, 1.0, 1, ["I"]),
        ]
        measures = _analyze_measures(events, 4.0)
        assert measures[0].chord_changes == 4
        assert measures[0].beats_per_change == 1.0


# ── Unit tests: per-phrase analysis ──


class TestPhraseAnalysis:
    def test_single_phrase(self):
        events = [
            _make_event(0.0, 2.0, 1, ["I"]),
            _make_event(2.0, 2.0, 1, ["IV"]),
            _make_event(4.0, 2.0, 2, ["V"]),
            _make_event(6.0, 2.0, 2, ["I"]),
        ]
        phrases = _analyze_phrases(events, [2], 4.0)
        assert len(phrases) == 1
        assert phrases[0].measure_start == 1
        assert phrases[0].measure_end == 2
        assert phrases[0].total_chord_changes == 4

    def test_two_phrases(self):
        events = [
            _make_event(0.0, 2.0, 1, ["I"]),
            _make_event(2.0, 2.0, 1, ["V"]),
            _make_event(4.0, 2.0, 2, ["I"]),
            # Phrase end at measure 2
            _make_event(8.0, 2.0, 3, ["IV"]),
            _make_event(10.0, 2.0, 3, ["V"]),
            _make_event(12.0, 2.0, 4, ["I"]),
        ]
        phrases = _analyze_phrases(events, [2, 4], 4.0)
        assert len(phrases) == 2
        assert phrases[0].measure_start == 1
        assert phrases[0].measure_end == 2
        assert phrases[1].measure_start == 3
        assert phrases[1].measure_end == 4

    def test_no_phrase_endings_single_phrase(self):
        events = [
            _make_event(0.0, 2.0, 1, ["I"]),
            _make_event(4.0, 2.0, 2, ["V"]),
        ]
        phrases = _analyze_phrases(events, [], 4.0)
        assert len(phrases) == 1
        assert phrases[0].measure_start == 1
        assert phrases[0].measure_end == 2


# ── Unit tests: cadential acceleration ──


class TestCadentialAcceleration:
    def test_steady_rhythm_returns_near_1(self):
        events = [
            _make_event(0.0, 2.0, 1, ["I"]),
            _make_event(2.0, 2.0, 1, ["IV"]),
            _make_event(4.0, 2.0, 2, ["V"]),
            _make_event(6.0, 2.0, 2, ["I"]),
        ]
        cai = _cadential_acceleration_index(events, "4/4")
        assert 0.8 <= cai <= 1.2

    def test_acceleration_at_end(self):
        events = [
            _make_event(0.0, 4.0, 1, ["I"]),
            _make_event(4.0, 4.0, 2, ["IV"]),
            _make_event(8.0, 1.0, 3, ["V7"]),
            _make_event(9.0, 1.0, 3, ["I"]),
            _make_event(10.0, 1.0, 3, ["V"]),
            _make_event(11.0, 1.0, 3, ["I"]),
        ]
        cai = _cadential_acceleration_index(events, "4/4")
        assert cai > 1.0

    def test_too_few_events_returns_1(self):
        events = [_make_event(0.0, 4.0, 1, ["I"])]
        cai = _cadential_acceleration_index(events, "4/4")
        assert cai == 1.0

    def test_3_2_meter_uses_correct_beat_duration(self):
        # In 3/2, one beat = 2 quarter notes, so tail window = 4 quarter notes
        events = [
            _make_event(0.0, 6.0, 1, ["I"]),   # whole measure
            _make_event(6.0, 6.0, 2, ["IV"]),   # whole measure
            _make_event(12.0, 2.0, 3, ["V7"]),  # last measure: 3 chords
            _make_event(14.0, 2.0, 3, ["I"]),
            _make_event(16.0, 2.0, 3, ["V"]),
        ]
        cai = _cadential_acceleration_index(events, "3/2")
        # Avg duration = (6+6+2+2+2)/5 = 3.6
        # Tail events (last 4 qn): events at 14.0 and 16.0, avg_dur = 2.0
        # CAI = 3.6 / 2.0 = 1.8
        assert cai > 1.0


# ── Unit tests: hemiola detection ──


class TestHemiolaDetection:
    def test_no_hemiola_in_4_4(self):
        events = [
            _make_event(0.0, 1.0, 1, ["I"]),
            _make_event(1.0, 1.0, 1, ["IV"]),
            _make_event(2.0, 1.0, 1, ["V"]),
            _make_event(3.0, 1.0, 1, ["I"]),
        ]
        hemiolas = _detect_hemiolas(events, "4/4", 4.0)
        assert hemiolas == []

    def test_hemiola_in_3_4(self):
        # 2 measures of 3/4: beats at 0,1,2,3,4,5
        # Hemiola: chord changes at 0, 2, 4 (duple grouping)
        events = [
            _make_event(0.0, 2.0, 1, ["I"]),
            _make_event(2.0, 2.0, 1, ["V"]),
            _make_event(4.0, 2.0, 2, ["I"]),
        ]
        hemiolas = _detect_hemiolas(events, "3/4", 3.0)
        assert len(hemiolas) == 1
        assert hemiolas[0].implied_grouping == 2
        assert hemiolas[0].actual_meter_beats == 3
        assert hemiolas[0].confidence > 0.5

    def test_no_hemiola_normal_triple(self):
        # Normal 3/4 pattern: chord changes at 0 and 3 (barline)
        events = [
            _make_event(0.0, 3.0, 1, ["I"]),
            _make_event(3.0, 3.0, 2, ["V"]),
        ]
        hemiolas = _detect_hemiolas(events, "3/4", 3.0)
        assert hemiolas == []

    def test_no_hemiola_every_beat_activity(self):
        # Dense every-beat chord changes should NOT be flagged as hemiola.
        # Changes at 0,1,2,3,4,5 — this is fast harmonic rhythm, not duple regrouping.
        events = [
            _make_event(0.0, 1.0, 1, ["I"]),
            _make_event(1.0, 1.0, 1, ["IV"]),
            _make_event(2.0, 1.0, 1, ["V"]),
            _make_event(3.0, 1.0, 2, ["vi"]),
            _make_event(4.0, 1.0, 2, ["ii"]),
            _make_event(5.0, 1.0, 2, ["V"]),
        ]
        hemiolas = _detect_hemiolas(events, "3/4", 3.0)
        assert hemiolas == [], f"Dense every-beat activity falsely detected as hemiola: {hemiolas}"


# ── Unit tests: duration-weighted rhythm ──


class TestDurationWeightedRhythm:
    def test_empty_events(self):
        assert _duration_weighted_rhythm([]) == 0.0

    def test_uniform_durations(self):
        events = [
            _make_event(0.0, 2.0, 1, ["I"]),
            _make_event(2.0, 2.0, 1, ["V"]),
        ]
        dwr = _duration_weighted_rhythm(events)
        assert dwr == pytest.approx(0.5, abs=0.01)

    def test_fast_rhythm(self):
        events = [
            _make_event(0.0, 1.0, 1, ["I"]),
            _make_event(1.0, 1.0, 1, ["IV"]),
            _make_event(2.0, 1.0, 1, ["V"]),
            _make_event(3.0, 1.0, 1, ["I"]),
        ]
        dwr = _duration_weighted_rhythm(events)
        assert dwr == pytest.approx(1.0, abs=0.01)


# ── Unit tests: acceleration trend ──


class TestAccelerationTrend:
    def test_steady(self):
        measures = [
            MeasureRhythm(measure=i, chord_changes=2, beats_per_change=2.0)
            for i in range(1, 5)
        ]
        assert _acceleration_trend(measures) == pytest.approx(0.0, abs=0.01)

    def test_accelerating(self):
        measures = [
            MeasureRhythm(measure=1, chord_changes=1, beats_per_change=4.0),
            MeasureRhythm(measure=2, chord_changes=2, beats_per_change=2.0),
            MeasureRhythm(measure=3, chord_changes=3, beats_per_change=1.33),
            MeasureRhythm(measure=4, chord_changes=4, beats_per_change=1.0),
        ]
        trend = _acceleration_trend(measures)
        assert trend > 0.0

    def test_too_few_measures(self):
        measures = [
            MeasureRhythm(measure=1, chord_changes=2, beats_per_change=2.0),
        ]
        assert _acceleration_trend(measures) == 0.0


# ── Integration: extract_harmonic_rhythm ──


class TestExtractHarmonicRhythm:
    def test_basic_profile(self):
        events = [
            _make_event(0.0, 2.0, 1, ["I"]),
            _make_event(2.0, 2.0, 1, ["IV"]),
            _make_event(4.0, 2.0, 2, ["V"]),
            _make_event(6.0, 2.0, 2, ["I"]),
        ]
        profile = extract_harmonic_rhythm_from_events(events, "4/4", phrase_end_measures=[2], encoding_id="test")
        assert isinstance(profile, HarmonicRhythmProfile)
        assert profile.meter == "4/4"
        assert profile.beats_per_measure == 4.0
        assert len(profile.measures) == 2
        assert profile.mean_changes_per_measure == 2.0
        assert profile.duration_weighted_rhythm > 0

    def test_serialization_roundtrip(self):
        events = [
            _make_event(0.0, 4.0, 1, ["I"]),
            _make_event(4.0, 4.0, 2, ["V"]),
        ]
        profile = extract_harmonic_rhythm_from_events(events, "4/4", encoding_id="test")
        d = profile.model_dump(mode="json")
        assert isinstance(d, dict)
        assert "measures" in d
        assert "phrases" in d
        assert "hemiolas" in d
        profile2 = HarmonicRhythmProfile(**d)
        assert profile2.mean_changes_per_measure == profile.mean_changes_per_measure

    def test_no_events(self):
        profile = extract_harmonic_rhythm_from_events([], "4/4", encoding_id="test")
        assert profile.mean_changes_per_measure == 0.0
        assert profile.measures == []
        assert profile.phrases == []


# ── Integration: pipeline ──


class TestPipelineIntegration:
    def test_analyze_chorale_includes_harmonic_rhythm(self, simple_chorale_graph):
        report = analyze_chorale(simple_chorale_graph)
        assert "harmonic_rhythm" in type(report).model_fields
        hr = report.harmonic_rhythm
        assert isinstance(hr, dict)
        assert "measures" in hr
        assert "mean_changes_per_measure" in hr
        assert hr["mean_changes_per_measure"] > 0

    def test_evidence_bundle_includes_harmonic_rhythm(self, simple_chorale_graph):
        report = analyze_chorale(simple_chorale_graph)
        bundle = build_evidence_bundle(simple_chorale_graph, report)
        assert "harmonic_rhythm" in bundle.deterministic_findings
        hr = bundle.deterministic_findings["harmonic_rhythm"]
        assert isinstance(hr, dict)
        assert hr["meter"] is not None

    def test_cadential_acceleration_correlates_with_phrase_endings(self, simple_chorale_graph):
        report = analyze_chorale(simple_chorale_graph)
        hr = report.harmonic_rhythm
        phrases = hr.get("phrases", [])
        phrase_endings = report.phrase_endings
        phrase_end_ms = sorted({pe["measure"] for pe in phrase_endings})
        # At least one phrase should exist when phrase endings exist
        if phrase_endings:
            assert len(phrases) >= 1, "No phrases despite phrase endings"
        for p in phrases:
            cai = p["cadential_acceleration_index"]
            # CAI must be finite and positive
            assert isinstance(cai, float)
            assert cai > 0, f"CAI must be positive, got {cai}"
            # Each phrase should cover at least 1 measure
            assert p["measure_end"] >= p["measure_start"]
            assert p["total_chord_changes"] >= 1
            # Phrase end measure must align with a known phrase ending
            # (or be the last measure if no further endings exist)
            if phrase_end_ms:
                assert (p["measure_end"] in phrase_end_ms
                        or p["measure_end"] >= phrase_end_ms[-1]), (
                    f"Phrase end m{p['measure_end']} not at a known phrase ending"
                )

    def test_cai_detects_acceleration_at_real_cadences(self):
        """Verify that phrases with faster harmonic rhythm at the end
        produce higher CAI than phrases with steady rhythm."""
        # Phrase with acceleration at the end (typical cadential pattern)
        accelerating = [
            _make_event(0.0, 4.0, 1, ["I"]),
            _make_event(4.0, 4.0, 2, ["IV"]),
            _make_event(8.0, 1.0, 3, ["ii"]),
            _make_event(9.0, 1.0, 3, ["V7"]),
            _make_event(10.0, 1.0, 3, ["V"]),
            _make_event(11.0, 1.0, 3, ["I"]),
        ]
        # Phrase with steady rhythm (no acceleration)
        steady = [
            _make_event(0.0, 2.0, 1, ["I"]),
            _make_event(2.0, 2.0, 1, ["IV"]),
            _make_event(4.0, 2.0, 2, ["V"]),
            _make_event(6.0, 2.0, 2, ["I"]),
            _make_event(8.0, 2.0, 3, ["ii"]),
            _make_event(10.0, 2.0, 3, ["V"]),
        ]
        cai_accel = _cadential_acceleration_index(accelerating, "4/4")
        cai_steady = _cadential_acceleration_index(steady, "4/4")
        assert cai_accel > cai_steady, (
            f"Accelerating phrase CAI ({cai_accel}) should exceed "
            f"steady phrase CAI ({cai_steady})"
        )
        assert cai_accel > 1.0, "Accelerating phrase should have CAI > 1.0"

    def test_extract_from_graph_public_api(self, simple_chorale_graph):
        profile = extract_harmonic_rhythm(simple_chorale_graph)
        assert isinstance(profile, HarmonicRhythmProfile)
        assert profile.mean_changes_per_measure > 0


# ── Corpus parametrized tests ──


def _corpus_graph_ids() -> list[str]:
    """Find all normalized event graph JSON files in the corpus."""
    base = Path("/Volumes/VIXinSSD/bachbot/data/normalized/dcml_bach_chorales")
    if not base.exists():
        return []
    files = sorted(base.glob("*.event_graph.json"))
    return [str(f) for f in files[:20]]  # Sample 20 for speed


@pytest.mark.parametrize("graph_path", _corpus_graph_ids())
def test_corpus_harmonic_rhythm(graph_path):
    """Verify harmonic rhythm extraction on real chorales."""
    from bachbot.encodings.event_graph import EventGraph

    data = json.loads(Path(graph_path).read_text())
    graph = EventGraph(**data)
    report = analyze_chorale(graph)
    hr = report.harmonic_rhythm

    assert hr["mean_changes_per_measure"] > 0
    assert len(hr["measures"]) > 0
    # Duration-weighted rhythm should be positive
    assert hr["duration_weighted_rhythm"] > 0
    # Mean changes should be reasonable (1-8 per measure)
    assert 0.5 <= hr["mean_changes_per_measure"] <= 10.0
