"""Harmonic rhythm extraction and metric dissonance detection.

Analyzes the rate of harmonic change relative to metric structure.
Detects hemiola, cadential acceleration, and per-phrase/per-measure profiles.
"""

from __future__ import annotations

import math
from collections import defaultdict

from pydantic import Field

from bachbot.models.base import BachbotModel
from bachbot.models.harmonic_event import HarmonicEvent


# ── Models ──


class MeasureRhythm(BachbotModel):
    """Harmonic rhythm data for a single measure."""

    measure: int
    chord_changes: int
    beats_per_change: float
    metric_positions: list[float] = Field(default_factory=list)
    chords: list[str] = Field(default_factory=list)


class PhraseRhythm(BachbotModel):
    """Harmonic rhythm data for a phrase (segment between phrase endings)."""

    phrase_index: int
    measure_start: int
    measure_end: int
    avg_changes_per_measure: float
    cadential_acceleration_index: float
    total_chord_changes: int
    duration_quarters: float


class HemiolaDetection(BachbotModel):
    """A detected hemiola: harmonic rhythm implies a different grouping."""

    measure_start: int
    measure_end: int
    implied_grouping: int
    actual_meter_beats: int
    confidence: float


class HarmonicRhythmProfile(BachbotModel):
    """Complete harmonic rhythm analysis for a chorale."""

    encoding_id: str
    meter: str
    beats_per_measure: float
    measures: list[MeasureRhythm] = Field(default_factory=list)
    phrases: list[PhraseRhythm] = Field(default_factory=list)
    hemiolas: list[HemiolaDetection] = Field(default_factory=list)
    mean_changes_per_measure: float = 0.0
    duration_weighted_rhythm: float = 0.0
    overall_acceleration_trend: float = 0.0


# ── Helpers ──


def _parse_meter(meter: str | None) -> tuple[int, int]:
    """Parse meter string like '3/4' into (numerator, denominator)."""
    if not meter:
        return 4, 4
    parts = meter.split("/")
    if len(parts) == 2:
        try:
            num, denom = int(parts[0]), int(parts[1])
            if denom > 0 and num > 0:
                return num, denom
        except ValueError:
            pass
    return 4, 4


def _beats_per_measure(meter: str | None) -> float:
    """Compute beats per measure in quarter-note units."""
    num, denom = _parse_meter(meter)
    return num * (4.0 / denom)


def _top_chord(event: HarmonicEvent) -> str:
    """Get the top Roman numeral candidate for an event."""
    if event.roman_numeral_candidate_set:
        return event.roman_numeral_candidate_set[0]
    return "?"


def _event_measure(event: HarmonicEvent) -> int:
    """Extract measure number from ref_id."""
    parts = event.ref_id.rsplit("m", 1)
    if len(parts) == 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 1


def _metric_position(event: HarmonicEvent, bpm: float) -> float:
    """Compute the metric position within the measure (0-based beat)."""
    measure = _event_measure(event)
    measure_onset = (measure - 1) * bpm
    return event.onset - measure_onset


# ── Per-measure analysis ──


def _analyze_measures(
    events: list[HarmonicEvent],
    bpm: float,
) -> list[MeasureRhythm]:
    """Compute per-measure harmonic rhythm."""
    by_measure: dict[int, list[HarmonicEvent]] = defaultdict(list)
    for e in events:
        by_measure[_event_measure(e)].append(e)

    results: list[MeasureRhythm] = []
    for measure in sorted(by_measure):
        measure_events = by_measure[measure]
        # Count chord changes: distinct consecutive chords
        chords: list[str] = []
        for e in measure_events:
            label = _top_chord(e)
            if not chords or label != chords[-1]:
                chords.append(label)

        changes = len(chords)
        beats_per_change = bpm / changes if changes > 0 else bpm

        # Only report metric positions of chord *changes* (not repeated chords)
        change_positions: list[float] = []
        prev_label = None
        for e in measure_events:
            label = _top_chord(e)
            if label != prev_label:
                change_positions.append(_metric_position(e, bpm))
                prev_label = label

        results.append(MeasureRhythm(
            measure=measure,
            chord_changes=changes,
            beats_per_change=round(beats_per_change, 3),
            metric_positions=[round(p, 3) for p in change_positions],
            chords=chords,
        ))
    return results


# ── Per-phrase analysis ──


def _analyze_phrases(
    events: list[HarmonicEvent],
    phrase_end_measures: list[int],
    bpm: float,
    meter: str | None = None,
) -> list[PhraseRhythm]:
    """Compute per-phrase harmonic rhythm with cadential acceleration."""
    if not events:
        return []

    all_measures = sorted({_event_measure(e) for e in events})
    if not all_measures:
        return []

    # Build phrase boundaries from phrase endings
    boundaries: list[tuple[int, int]] = []
    sorted_ends = sorted(set(phrase_end_measures))
    start = all_measures[0]
    for end_m in sorted_ends:
        if end_m >= start:
            boundaries.append((start, end_m))
            start = end_m + 1
    # Add trailing phrase if events continue past last ending
    if start <= all_measures[-1]:
        boundaries.append((start, all_measures[-1]))

    # If no phrase endings detected, treat entire piece as one phrase
    if not boundaries:
        boundaries = [(all_measures[0], all_measures[-1])]

    by_measure: dict[int, list[HarmonicEvent]] = defaultdict(list)
    for e in events:
        by_measure[_event_measure(e)].append(e)

    phrases: list[PhraseRhythm] = []
    for idx, (m_start, m_end) in enumerate(boundaries):
        phrase_events = [e for e in events
                         if m_start <= _event_measure(e) <= m_end]
        if not phrase_events:
            continue

        # Count chord changes across phrase
        chord_seq: list[str] = []
        for e in phrase_events:
            label = _top_chord(e)
            if not chord_seq or label != chord_seq[-1]:
                chord_seq.append(label)

        n_measures = m_end - m_start + 1
        total_changes = len(chord_seq)
        avg_changes = total_changes / n_measures if n_measures > 0 else 0.0

        # Cadential acceleration: compare last 2 beats to phrase average
        total_dur = sum(e.duration for e in phrase_events)
        cai = _cadential_acceleration_index(phrase_events, meter)

        phrases.append(PhraseRhythm(
            phrase_index=idx,
            measure_start=m_start,
            measure_end=m_end,
            avg_changes_per_measure=round(avg_changes, 3),
            cadential_acceleration_index=round(cai, 3),
            total_chord_changes=total_changes,
            duration_quarters=round(total_dur, 3),
        ))

    return phrases


def _cadential_acceleration_index(
    phrase_events: list[HarmonicEvent],
    meter: str | None,
) -> float:
    """Compute cadential acceleration index.

    Ratio of average harmonic rhythm in the last 2 beats vs. the phrase average.
    Values > 1.0 indicate acceleration at the cadence.
    """
    if len(phrase_events) < 3:
        return 1.0

    # Average duration across all events
    durations = [e.duration for e in phrase_events]
    avg_dur = sum(durations) / len(durations)
    if avg_dur <= 0:
        return 1.0

    # Average duration of last 2-beat window of events
    total_onset_span = phrase_events[-1].onset - phrase_events[0].onset
    if total_onset_span <= 0:
        return 1.0

    # Compute tail window as exactly 2 metric beats in quarter-note units.
    # One beat = 4/denom quarter notes (e.g., 3/4 → 1.0, 3/2 → 2.0, 6/8 → 0.5).
    _, denom = _parse_meter(meter)
    beat_duration = 4.0 / denom
    tail_window = 2.0 * beat_duration
    cutoff = phrase_events[-1].onset + phrase_events[-1].duration - tail_window
    # Include events that overlap the tail window (not just those starting in it)
    tail_events = [e for e in phrase_events if e.onset + e.duration > cutoff]
    if len(tail_events) < 2:
        return 1.0

    tail_avg_dur = sum(e.duration for e in tail_events) / len(tail_events)
    if tail_avg_dur <= 0:
        return 1.0

    # Acceleration = shorter durations at end → avg_dur / tail_avg_dur > 1
    return avg_dur / tail_avg_dur


# ── Hemiola detection ──


def _detect_hemiolas(
    events: list[HarmonicEvent],
    meter: str | None,
    bpm: float,
) -> list[HemiolaDetection]:
    """Detect hemiola patterns in triple-meter chorales.

    Hemiola: in 3/4 or 3/2, harmonic changes imply grouping in 2 instead of 3.
    Look for windows where chord changes align with beat pairs rather than
    the triple-beat meter.
    """
    num, denom = _parse_meter(meter)
    if num != 3:
        return []  # Hemiola detection only meaningful in triple meter

    by_measure: dict[int, list[HarmonicEvent]] = defaultdict(list)
    for e in events:
        by_measure[_event_measure(e)].append(e)

    sorted_measures = sorted(by_measure)
    hemiolas: list[HemiolaDetection] = []

    # Scan pairs of adjacent measures for hemiola pattern
    # In 3/4 hemiola: 2 measures of 3/4 regroup as 3 groups of 2 beats
    for i in range(len(sorted_measures) - 1):
        m1 = sorted_measures[i]
        m2 = sorted_measures[i + 1]
        if m2 != m1 + 1:
            continue

        events_m1 = by_measure[m1]
        events_m2 = by_measure[m2]
        combined = events_m1 + events_m2

        # Get metric positions of chord changes across 2-measure span
        change_positions: list[float] = []
        prev_chord = None
        base_onset = combined[0].onset if combined else 0.0
        for e in combined:
            label = _top_chord(e)
            if label != prev_chord:
                change_positions.append(e.onset - base_onset)
                prev_chord = label

        if len(change_positions) < 3:
            continue

        # Check if changes align with duple grouping (every 2 beats)
        # In 3/4: 2 measures = 6 quarter beats. Hemiola groups: 0, 2, 4
        # Non-duple positions: 1, 3, 5
        beat_unit = 4.0 / denom
        span = 2 * bpm  # total quarter-note span of the 2-measure window
        duple_beats = [i * 2 * beat_unit for i in range(3)]  # 0, 2, 4 for 3/4
        non_duple_beats = [b for b in
                           [i * beat_unit for i in range(int(span / beat_unit))]
                           if not any(abs(b - db) < 0.01 for db in duple_beats)]

        tolerance = 0.5 * beat_unit
        duple_hits = sum(
            1 for pos in change_positions
            if any(abs(pos - db) < tolerance for db in duple_beats)
        )
        non_duple_hits = sum(
            1 for pos in change_positions
            if any(abs(pos - ndb) < tolerance for ndb in non_duple_beats)
        )

        # Hemiola requires:
        # 1. At least 3 changes align with duple beats
        # 2. Non-duple positions have few changes (dense every-beat != hemiola)
        if (duple_hits >= 3
                and non_duple_hits <= 1
                and duple_hits > len(change_positions) * 0.5):
            confidence = min(duple_hits / len(change_positions), 0.95)
            hemiolas.append(HemiolaDetection(
                measure_start=m1,
                measure_end=m2,
                implied_grouping=2,
                actual_meter_beats=num,
                confidence=round(confidence, 3),
            ))

    return hemiolas


# ── Duration-weighted harmonic rhythm ──


def _duration_weighted_rhythm(events: list[HarmonicEvent]) -> float:
    """Compute duration-weighted average harmonic rhythm.

    Weight each chord change duration inversely — shorter durations
    contribute more to the "activity" of harmonic rhythm.
    Returns average changes per quarter-note beat.
    """
    if not events:
        return 0.0

    # Count distinct chord changes and their durations
    changes: list[float] = []
    prev_chord = None
    current_dur = 0.0
    for e in events:
        label = _top_chord(e)
        if label != prev_chord:
            if prev_chord is not None:
                changes.append(current_dur)
            current_dur = e.duration
            prev_chord = label
        else:
            current_dur += e.duration
    if prev_chord is not None:
        changes.append(current_dur)

    if not changes:
        return 0.0

    total_dur = sum(changes)
    if total_dur <= 0:
        return 0.0

    # Changes per quarter note
    return len(changes) / total_dur


# ── Overall acceleration trend ──


def _acceleration_trend(measure_rhythms: list[MeasureRhythm]) -> float:
    """Compute linear trend in chord changes per measure.

    Positive = accelerating (more changes toward end).
    Negative = decelerating.
    Near zero = steady.
    Returns slope of linear regression on chord_changes vs measure index.
    """
    n = len(measure_rhythms)
    if n < 3:
        return 0.0

    xs = list(range(n))
    ys = [m.chord_changes for m in measure_rhythms]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return num / den


# ── Public API ──


def extract_harmonic_rhythm_from_events(
    events: list[HarmonicEvent],
    meter: str | None,
    phrase_end_measures: list[int] | None = None,
    encoding_id: str = "",
) -> HarmonicRhythmProfile:
    """Extract harmonic rhythm profile from pre-computed harmonic events.

    Used internally when the caller already has harmony events and phrase data
    (e.g., from the analysis pipeline). For the standard public API, use
    ``extract_harmonic_rhythm(graph)``.

    Args:
        events: Harmonic events from summarize_harmony().
        meter: Time signature string (e.g., "4/4", "3/4").
        phrase_end_measures: Measures where phrases end (from phrase detection).
        encoding_id: Encoding ID for labeling.

    Returns:
        HarmonicRhythmProfile with per-measure, per-phrase, and hemiola data.
    """
    bpm = _beats_per_measure(meter)

    measures = _analyze_measures(events, bpm)
    phrases = _analyze_phrases(events, phrase_end_measures or [], bpm, meter=meter)
    hemiolas = _detect_hemiolas(events, meter, bpm)

    mean_cpm = (
        sum(m.chord_changes for m in measures) / len(measures)
        if measures else 0.0
    )

    return HarmonicRhythmProfile(
        encoding_id=encoding_id,
        meter=meter or "4/4",
        beats_per_measure=bpm,
        measures=measures,
        phrases=phrases,
        hemiolas=hemiolas,
        mean_changes_per_measure=round(mean_cpm, 3),
        duration_weighted_rhythm=round(_duration_weighted_rhythm(events), 3),
        overall_acceleration_trend=round(_acceleration_trend(measures), 4),
    )


def extract_harmonic_rhythm(graph: "EventGraph") -> HarmonicRhythmProfile:
    """Extract harmonic rhythm profile from an EventGraph.

    This is the primary public API matching the acceptance criteria:
    ``extract_harmonic_rhythm(graph) -> HarmonicRhythmProfile``.

    Runs summarize_harmony, phrase detection, and harmonic rhythm extraction.
    """
    from bachbot.analysis.form.phrase import phrase_end_measures
    from bachbot.analysis.harmony.cadence import detect_cadences, summarize_harmony

    harmony = summarize_harmony(graph)
    cadences = detect_cadences(graph)
    pe_measures = phrase_end_measures(graph, cadences=cadences)
    return extract_harmonic_rhythm_from_events(
        harmony,
        meter=graph.meter,
        phrase_end_measures=pe_measures,
        encoding_id=graph.metadata.encoding_id,
    )
