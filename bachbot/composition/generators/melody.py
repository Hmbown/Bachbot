"""Chorale melody generation from harmonic plans via Viterbi search."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from bachbot.composition.generators.pattern_fill import CHORD_INTERVALS, NOTE_TO_PC, _resolve_secondary_dominant
from bachbot.encodings.musicxml_io import midi_to_note_name
from bachbot.models.base import BachbotModel, TypedNote


# Major / minor scale pitch classes (relative to tonic = 0)
_MAJOR_SCALE_PCS = frozenset({0, 2, 4, 5, 7, 9, 11})
_MINOR_SCALE_PCS = frozenset({0, 2, 3, 5, 7, 8, 10})


class HarmonicPlanEntry(BachbotModel):
    """One slot in a harmonic plan: a chord at a particular time."""

    onset: float
    duration: float
    roman_numeral: str
    local_key: str = "C"
    mode: str = "major"
    is_cadence: bool = False


class MelodyConfig(BachbotModel):
    """Configuration for melody generation."""

    soprano_low: int = 60   # C4
    soprano_high: int = 79  # G5
    seed: int = 42


# ---------------------------------------------------------------------------
# Chord-tone helpers
# ---------------------------------------------------------------------------

def _chord_pcs_for_entry(entry: HarmonicPlanEntry) -> set[int]:
    """Return absolute pitch classes for the roman numeral in the given key."""
    tonic_pc = NOTE_TO_PC.get(entry.local_key, 0)
    label = entry.roman_numeral

    # Try CHORD_INTERVALS first (covers triads, sevenths, named sec doms)
    intervals = CHORD_INTERVALS.get(label)
    if intervals is None:
        # Try dynamic secondary dominant resolution
        intervals = _resolve_secondary_dominant(label)
    if intervals is None:
        # Fallback: just tonic triad
        intervals = (0, 4, 7)

    return {(tonic_pc + pc) % 12 for pc in intervals}


def _scale_pcs_for_entry(entry: HarmonicPlanEntry) -> set[int]:
    """Return absolute pitch classes for the scale of the given key/mode."""
    tonic_pc = NOTE_TO_PC.get(entry.local_key, 0)
    template = _MAJOR_SCALE_PCS if entry.mode == "major" else _MINOR_SCALE_PCS
    return {(tonic_pc + pc) % 12 for pc in template}


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

def _soprano_candidates(
    entry: HarmonicPlanEntry,
    low: int,
    high: int,
) -> list[tuple[int, bool]]:
    """Return (midi, is_chord_tone) pairs for soprano candidates in range.

    Chord tones are included directly.  Scale tones that are one step away
    from a chord tone are included as passing/neighbor candidates.
    """
    chord_pcs = _chord_pcs_for_entry(entry)
    scale_pcs = _scale_pcs_for_entry(entry)
    candidates: list[tuple[int, bool]] = []
    for midi in range(low, high + 1):
        pc = midi % 12
        if pc in chord_pcs:
            candidates.append((midi, True))
        elif pc in scale_pcs:
            # Accept scale tones that are 1-2 semitones from any chord tone
            for ct in chord_pcs:
                if abs(pc - ct) <= 2 or abs(pc - ct) >= 10:  # semitone wrap
                    candidates.append((midi, False))
                    break
    return candidates


# ---------------------------------------------------------------------------
# Viterbi scoring
# ---------------------------------------------------------------------------

_INF = float("inf")


def _interval_cost(prev_midi: int, curr_midi: int) -> float:
    """Melodic interval cost — prefers stepwise motion."""
    diff = abs(curr_midi - prev_midi)
    if diff == 0:
        return 3.0   # repeated note
    if diff <= 2:
        return 0.0   # stepwise
    if diff <= 4:
        return 2.0   # small leap
    if diff <= 7:
        return 5.0   # medium leap
    return 15.0       # large leap


def _leap_direction(prev_midi: int, curr_midi: int) -> int:
    """Return +1 for ascending, -1 for descending, 0 for unison."""
    if curr_midi > prev_midi:
        return 1
    if curr_midi < prev_midi:
        return -1
    return 0


def generate_melody(
    plan: list[HarmonicPlanEntry],
    *,
    config: MelodyConfig | None = None,
) -> list[TypedNote]:
    """Generate a soprano melody from a harmonic plan using Viterbi search.

    Parameters
    ----------
    plan:
        Ordered harmonic plan entries.
    config:
        Optional melody configuration (range, seed).

    Returns
    -------
    list[TypedNote]
        Soprano melody as TypedNote objects.
    """
    if not plan:
        return []

    cfg = config or MelodyConfig()
    rng = random.Random(cfg.seed)

    # Build candidate lists for each time step
    step_candidates: list[list[tuple[int, bool]]] = []
    for entry in plan:
        cands = _soprano_candidates(entry, cfg.soprano_low, cfg.soprano_high)
        if not cands:
            # Fallback: all pitches in range (shouldn't happen with normal keys)
            cands = [(m, False) for m in range(cfg.soprano_low, cfg.soprano_high + 1)]
        step_candidates.append(cands)

    n_steps = len(plan)

    # Viterbi forward pass
    # cost[t][j] = min cost to reach candidate j at step t
    # back[t][j] = index of best predecessor at step t-1
    cost: list[list[float]] = []
    back: list[list[int]] = []

    # Step 0 — initialize
    cands_0 = step_candidates[0]
    cost_0: list[float] = []
    for midi, is_ct in cands_0:
        c = 0.0 if is_ct else 4.0
        # Slight preference for middle of range
        mid = (cfg.soprano_low + cfg.soprano_high) / 2
        c += abs(midi - mid) * 0.1
        # Small random tiebreaker for variety
        c += rng.random() * 0.5
        cost_0.append(c)
    cost.append(cost_0)
    back.append([-1] * len(cands_0))

    for t in range(1, n_steps):
        cands_prev = step_candidates[t - 1]
        cands_curr = step_candidates[t]
        cost_t: list[float] = []
        back_t: list[int] = []
        entry = plan[t]

        # Track which predecessor produced a large leap (for contrary motion check)
        for j, (midi_j, is_ct_j) in enumerate(cands_curr):
            best_cost = _INF
            best_prev = 0
            for k, (midi_k, _is_ct_k) in enumerate(cands_prev):
                c = cost[t - 1][k]
                # Interval cost
                c += _interval_cost(midi_k, midi_j)
                # Non-chord-tone penalty
                if not is_ct_j:
                    c += 4.0
                # Cadence: strong preference for chord tone
                if entry.is_cadence and not is_ct_j:
                    c += 20.0
                # After large leap: prefer contrary stepwise
                if t >= 2:
                    # Get the note two steps back from the back pointer
                    prev_prev_idx = back[t - 1][k]
                    if prev_prev_idx >= 0:
                        midi_pp = step_candidates[t - 2][prev_prev_idx][0]
                        leap = abs(midi_k - midi_pp)
                        if leap > 4:
                            direction_leap = _leap_direction(midi_pp, midi_k)
                            direction_resolve = _leap_direction(midi_k, midi_j)
                            step_resolve = abs(midi_j - midi_k)
                            if direction_resolve == direction_leap or step_resolve > 2:
                                c += 6.0  # Penalty for not resolving leap
                # Small random tiebreaker
                c += rng.random() * 0.3
                if c < best_cost:
                    best_cost = c
                    best_prev = k
            cost_t.append(best_cost)
            back_t.append(best_prev)
        cost.append(cost_t)
        back.append(back_t)

    # Backtrack
    # Find best final candidate
    final_costs = cost[-1]
    best_final = min(range(len(final_costs)), key=lambda i: final_costs[i])
    path: list[int] = [0] * n_steps
    path[-1] = best_final
    for t in range(n_steps - 2, -1, -1):
        path[t] = back[t + 1][path[t + 1]]

    # Convert to TypedNote list
    notes: list[TypedNote] = []
    # Track cumulative offset for measure/beat calculation
    for t, entry in enumerate(plan):
        cand_idx = path[t]
        midi_val = step_candidates[t][cand_idx][0]
        # Compute measure and beat from onset
        # Assume 4/4 meter: measure = floor(onset / 4) + 1, beat = (onset % 4) + 1
        measure = int(entry.onset // 4) + 1
        beat = (entry.onset % 4) + 1.0
        note = TypedNote(
            pitch=midi_to_note_name(midi_val),
            midi=midi_val,
            duration_quarters=entry.duration,
            offset_quarters=entry.onset,
            measure_number=measure,
            beat=beat,
            voice_id="S",
        )
        notes.append(note)
    return notes


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def plan_from_chord_sequence(
    chords: list[str],
    *,
    key: str = "C",
    mode: str = "major",
    meter: str = "4/4",
    beats_per_chord: float = 1.0,
) -> list[HarmonicPlanEntry]:
    """Create a harmonic plan from a simple chord list.

    Parameters
    ----------
    chords:
        Roman numeral labels, e.g. ``["I", "IV", "V", "I"]``.
    key:
        Tonic pitch name.
    mode:
        ``"major"`` or ``"minor"``.
    meter:
        Time signature string (used for display; beat grouping is derived
        from *beats_per_chord*).
    beats_per_chord:
        Duration in quarter notes for each chord.

    Returns
    -------
    list[HarmonicPlanEntry]
    """
    plan: list[HarmonicPlanEntry] = []
    onset = 0.0
    for i, chord in enumerate(chords):
        plan.append(HarmonicPlanEntry(
            onset=onset,
            duration=beats_per_chord,
            roman_numeral=chord,
            local_key=key,
            mode=mode,
            is_cadence=(i == len(chords) - 1),
        ))
        onset += beats_per_chord
    return plan


def plan_from_bundle(bundle_path_or_dict: str | Path | dict) -> list[HarmonicPlanEntry]:
    """Extract a harmonic plan from an evidence bundle.

    Reads ``deterministic_findings.harmony`` from the bundle and converts
    each harmonic event into a :class:`HarmonicPlanEntry`.

    Parameters
    ----------
    bundle_path_or_dict:
        Path to a JSON evidence bundle file, or an already-loaded dict.

    Returns
    -------
    list[HarmonicPlanEntry]
    """
    if isinstance(bundle_path_or_dict, (str, Path)):
        with open(bundle_path_or_dict, encoding="utf-8") as fh:
            bundle = json.load(fh)
    else:
        bundle = bundle_path_or_dict

    harmony = bundle.get("deterministic_findings", {}).get("harmony", [])
    plan: list[HarmonicPlanEntry] = []
    for evt in harmony:
        candidates = evt.get("roman_numeral_candidate_set", [])
        if not candidates:
            continue
        roman = candidates[0]
        local_key_str = evt.get("local_key", "C major")
        parts = local_key_str.split()
        tonic = parts[0] if parts else "C"
        mode = parts[1] if len(parts) > 1 else "major"
        plan.append(HarmonicPlanEntry(
            onset=evt.get("onset", 0.0),
            duration=evt.get("duration", 1.0),
            roman_numeral=roman,
            local_key=tonic,
            mode=mode,
            is_cadence=False,
        ))

    # Mark last entry of each phrase as cadence (simple heuristic: last entry)
    if plan:
        plan[-1].is_cadence = True

    return plan
