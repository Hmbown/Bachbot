"""Figured bass realization engine.

Given a bass line with figured bass symbols, generates the upper three voices
(soprano, alto, tenor) using Viterbi search with SATB voice-leading constraints.

This is the inverse of the chorale harmonizer in ``pattern_fill.py``, which
takes a soprano melody and generates alto/tenor/bass.
"""

from __future__ import annotations

import re
from itertools import product

from bachbot.composition.generators.pattern_fill import (
    RANGES,
    _has_forbidden_parallel,
    _motion,
)
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.encodings.musicxml_io import midi_to_note_name
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice

NOTE_TO_PC = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}

# Diatonic scales as semitone offsets from tonic
_MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)  # 1 2 3 4 5 6 7
_MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)  # natural minor


def _diatonic_interval(bass_pc: int, generic_interval: int, key_tonic_pc: int, mode: str) -> int:
    """Compute the semitone interval for a diatonic generic interval above bass.

    *generic_interval* is 1-based (2 = second, 3 = third, etc.).
    Returns the semitone distance above bass_pc within the key's diatonic scale.

    The target pitch class is determined by counting scale degrees from the
    bass note's position in the key.  The bass note itself need not be a
    diatonic pitch — its nearest scale degree is used only to find the
    correct generic-interval target.  The returned semitone distance is
    always measured from the *actual* bass pitch class.
    """
    scale = _MAJOR_SCALE if mode == "major" else _MINOR_SCALE
    # Find where bass sits relative to the key tonic
    bass_degree = (bass_pc - key_tonic_pc) % 12
    # Find the closest scale degree index.  On ties, prefer the degree
    # *above* the bass (chromatic bass notes are usually lowered scale
    # degrees, e.g. Bb in C major is a lowered 7th).
    best_degree_idx = 0
    best_dist = 999
    for i, s in enumerate(scale):
        dist = min(abs(s - bass_degree), 12 - abs(s - bass_degree))
        if dist < best_dist or (dist == best_dist and (s - bass_degree) % 12 < (scale[best_degree_idx] - bass_degree) % 12):
            best_dist = dist
            best_degree_idx = i
    # The target degree index (count generic_interval - 1 scale steps up)
    target_idx = (best_degree_idx + generic_interval - 1) % 7
    # Target pitch class in absolute terms
    target_pc = (key_tonic_pc + scale[target_idx]) % 12
    # Return interval from actual bass pc to target pc
    interval = (target_pc - bass_pc) % 12
    return interval


def _parse_figure_token(token: str) -> tuple[int, int]:
    """Parse a single figure token like '7', '#6', 'b3' into (generic_interval, accidental_shift).

    Returns (generic_interval, semitone_adjustment).
    """
    accidental = 0
    rest = token
    while rest and rest[0] in ("#", "b", "+", "-"):
        if rest[0] == "#" or rest[0] == "+":
            accidental += 1
        elif rest[0] == "b" or rest[0] == "-":
            accidental -= 1
        rest = rest[1:]
    if not rest:
        # Bare "#" means raised 3rd
        return (3, accidental)
    if rest.isdigit():
        return (int(rest), accidental)
    return (3, accidental)  # fallback


# Standard figure expansions: figure_str -> list of (generic_interval, accidental) tuples
_FIGURE_EXPANSIONS: dict[str, list[tuple[int, int]]] = {
    "": [(3, 0), (5, 0)],           # root position 5/3
    "5/3": [(3, 0), (5, 0)],
    "5": [(3, 0), (5, 0)],
    "6": [(3, 0), (6, 0)],
    "6/3": [(3, 0), (6, 0)],
    "6/4": [(4, 0), (6, 0)],
    "7": [(3, 0), (5, 0), (7, 0)],
    "7/5/3": [(3, 0), (5, 0), (7, 0)],
    "6/5": [(3, 0), (5, 0), (6, 0)],
    "6/5/3": [(3, 0), (5, 0), (6, 0)],
    "4/3": [(3, 0), (4, 0), (6, 0)],
    "4/2": [(2, 0), (4, 0), (6, 0)],
    "2": [(2, 0), (4, 0), (6, 0)],
}


def _parse_figures(figure_str: str) -> list[tuple[int, int]]:
    """Parse a figure string into a list of (generic_interval, accidental_shift) pairs.

    Handles standard shorthand ('6', '6/4', '7', etc.) and accidentals ('#6', 'b3').
    """
    figure_str = figure_str.strip()
    if figure_str in _FIGURE_EXPANSIONS:
        return list(_FIGURE_EXPANSIONS[figure_str])

    # Split by '/' and parse each token
    tokens = [t.strip() for t in figure_str.split("/") if t.strip()]
    if not tokens:
        return list(_FIGURE_EXPANSIONS[""])
    return [_parse_figure_token(t) for t in tokens]


def figures_to_pitch_classes(
    bass_midi: int,
    figure_str: str,
    key_tonic: str = "C",
    mode: str = "major",
) -> set[int]:
    """Convert a figure string and bass MIDI to allowed pitch classes (0-11).

    Always includes the bass pitch class. Adds pitch classes for each figured
    interval above the bass, computed diatonically within the key.
    """
    key_tonic_pc = NOTE_TO_PC.get(key_tonic, 0)
    bass_pc = bass_midi % 12
    result = {bass_pc}

    figures = _parse_figures(figure_str)
    for generic_interval, accidental in figures:
        semitone_interval = _diatonic_interval(bass_pc, generic_interval, key_tonic_pc, mode)
        pc = (bass_pc + semitone_interval + accidental) % 12
        result.add(pc)

    return result


def _candidate_pitches(allowed_pcs: set[int], low: int, high: int, preferred: int) -> list[int]:
    """Generate MIDI pitches in range whose pitch class is in allowed_pcs, sorted by proximity to preferred."""
    cands = [m for m in range(low, high + 1) if m % 12 in allowed_pcs]
    cands.sort(key=lambda m: (abs(m - preferred), m))
    return cands


def _generate_upper_voicings(
    bass_midi: int,
    allowed_pcs: set[int],
    targets: dict[str, int],
    max_per_beat: int = 80,
) -> list[tuple[int, int, int]]:
    """Generate (soprano, alto, tenor) candidate tuples for one beat.

    Constraints:
    - S in 60-79, A in 55-74, T in 48-67
    - S >= A >= T > bass
    - S-A <= 12, A-T <= 12 semitones
    """
    t_s = targets.get("Soprano:1", 72)
    t_a = targets.get("Alto:1", 64)
    t_t = targets.get("Tenor:1", 55)

    s_cands = _candidate_pitches(allowed_pcs, 60, 79, t_s)
    a_cands = _candidate_pitches(allowed_pcs, 55, 74, t_a)
    t_cands = _candidate_pitches(allowed_pcs, 48, 67, t_t)

    voicings: list[tuple[int, int, int]] = []
    for s in s_cands:
        for a in a_cands:
            if a > s or s - a > 12:
                continue
            for t in t_cands:
                if t > a or a - t > 12:
                    continue
                if t <= bass_midi:
                    continue
                voicings.append((s, a, t))

    if len(voicings) > max_per_beat:
        voicings.sort(key=lambda v: abs(v[0] - t_s) + abs(v[1] - t_a) + abs(v[2] - t_t))
        voicings = voicings[:max_per_beat]
    return voicings


def _viterbi_upper_voices(
    bass_notes: list[TypedNote],
    allowed_pcs_per_beat: list[set[int]],
    initial_targets: dict[str, int],
) -> list[dict[str, int]] | None:
    """Find minimum-cost upper voice sequence via Viterbi DP.

    Bass is fixed. Finds optimal soprano, alto, tenor paths that minimize
    voice motion while avoiding parallel 5ths/8ves.
    """
    n = len(bass_notes)
    if n == 0:
        return []

    PARALLEL_PENALTY = 1000.0
    SOPRANO_STEP_BONUS = -1.0  # mild preference for stepwise soprano
    SOPRANO_CONTRARY_BONUS = -2.0  # mild preference for contrary motion with bass
    INF = float("inf")

    targets = dict(initial_targets)
    candidates: list[list[tuple[int, int, int]]] = []
    for i in range(n):
        voicings = _generate_upper_voicings(
            bass_notes[i].midi, allowed_pcs_per_beat[i], targets,
        )
        if not voicings:
            return None
        candidates.append(voicings)
        targets = {
            "Soprano:1": voicings[0][0],
            "Alto:1": voicings[0][1],
            "Tenor:1": voicings[0][2],
        }

    # DP initialization
    init_s = initial_targets.get("Soprano:1", 72)
    init_a = initial_targets.get("Alto:1", 64)
    init_t = initial_targets.get("Tenor:1", 55)

    dp_prev = [
        abs(s - init_s) + abs(a - init_a) + abs(t - init_t)
        for s, a, t in candidates[0]
    ]
    bp: list[list[int]] = [[-1] * len(candidates[0])]

    for beat in range(1, n):
        curr = candidates[beat]
        prev = candidates[beat - 1]
        b_prev = bass_notes[beat - 1].midi
        b_curr = bass_notes[beat].midi
        bass_direction = _motion(b_prev, b_curr) if b_prev and b_curr else 0

        dp_curr = [INF] * len(curr)
        bp_curr = [-1] * len(curr)

        for j, (s_c, a_c, t_c) in enumerate(curr):
            curr_v = {"Soprano:1": s_c, "Alto:1": a_c, "Tenor:1": t_c, "Bass:1": b_curr}
            best = INF
            best_k = -1
            for k, (s_p, a_p, t_p) in enumerate(prev):
                if dp_prev[k] >= INF:
                    continue
                prev_v = {"Soprano:1": s_p, "Alto:1": a_p, "Tenor:1": t_p, "Bass:1": b_prev}
                motion = abs(s_c - s_p) + abs(a_c - a_p) + abs(t_c - t_p)

                # Soprano melodic bonus
                s_interval = abs(s_c - s_p)
                step_bonus = SOPRANO_STEP_BONUS if s_interval <= 2 else 0.0

                # Contrary motion bonus
                s_direction = _motion(s_p, s_c)
                contrary = SOPRANO_CONTRARY_BONUS if bass_direction != 0 and s_direction == -bass_direction else 0.0

                # Parallel check
                penalty = PARALLEL_PENALTY if _has_forbidden_parallel(prev_v, curr_v) else 0.0

                total = dp_prev[k] + motion + step_bonus + contrary + penalty
                if total < best:
                    best = total
                    best_k = k
            dp_curr[j] = best
            bp_curr[j] = best_k

        dp_prev = dp_curr
        bp.append(bp_curr)

    # Backtrack
    if all(c >= INF for c in dp_prev):
        return None
    best_final = min(range(len(dp_prev)), key=lambda i: dp_prev[i])
    path = [best_final]
    for beat in range(n - 1, 0, -1):
        path.append(bp[beat][path[-1]])
    path.reverse()

    return [
        {
            "Soprano:1": candidates[beat][path[beat]][0],
            "Alto:1": candidates[beat][path[beat]][1],
            "Tenor:1": candidates[beat][path[beat]][2],
            "Bass:1": bass_notes[beat].midi,
        }
        for beat in range(n)
    ]


def realize_figured_bass(
    bass_notes: list[TypedNote],
    figures: list[str],
    *,
    key_tonic: str = "C",
    mode: str = "major",
    meter: str = "4/4",
    artifact_id: str = "ART-fb-001",
) -> EventGraph:
    """Realize a figured bass line into an SATB EventGraph.

    Parameters
    ----------
    bass_notes : list[TypedNote]
        Bass voice notes with MIDI pitches, offsets, durations, measure numbers.
    figures : list[str]
        Figure strings, one per bass note. Use ``""`` or ``"-"`` for root position.
    key_tonic : str
        Key tonic (e.g., "C", "G", "Bb").
    mode : str
        "major" or "minor".
    meter : str
        Time signature string (e.g., "4/4").
    artifact_id : str
        Identifier for the output EventGraph.

    Returns
    -------
    EventGraph
        Four-voice SATB realization.
    """
    if len(bass_notes) != len(figures):
        raise ValueError(
            f"bass_notes ({len(bass_notes)}) and figures ({len(figures)}) must have same length"
        )
    if not bass_notes:
        raise ValueError("bass_notes must not be empty")

    # Normalize figure strings
    normalized_figures = [f if f != "-" else "" for f in figures]

    # Compute allowed pitch classes per beat
    allowed_pcs: list[set[int]] = []
    for note, fig in zip(bass_notes, normalized_figures):
        pcs = figures_to_pitch_classes(note.midi, fig, key_tonic, mode)
        allowed_pcs.append(pcs)

    # Initial targets for upper voices
    initial_targets = {"Soprano:1": 72, "Alto:1": 64, "Tenor:1": 55}

    # Viterbi search for upper voices
    voicing_sequence = _viterbi_upper_voices(bass_notes, allowed_pcs, initial_targets)

    if voicing_sequence is None:
        raise RuntimeError("Failed to find valid upper voice realization")

    # Build notes
    notes: list[TypedNote] = []
    for beat_idx, (bass_note, voicing) in enumerate(zip(bass_notes, voicing_sequence)):
        for voice_id, midi in voicing.items():
            notes.append(
                TypedNote(
                    pitch=midi_to_note_name(midi),
                    midi=midi,
                    duration_quarters=bass_note.duration_quarters,
                    offset_quarters=bass_note.offset_quarters,
                    measure_number=bass_note.measure_number,
                    beat=bass_note.beat,
                    voice_id=voice_id,
                    part_name=voice_id.split(":", 1)[0],
                    fermata=bass_note.fermata,
                )
            )

    # Build EventGraph
    max_measure = max(n.measure_number for n in bass_notes)
    section = Section(
        section_id=f"{artifact_id}:section:1",
        work_id=artifact_id,
        label="Figured bass realization",
        section_type="figured-bass-realization",
        measure_start=1,
        measure_end=max_measure,
    )
    metadata = EncodingMetadata(
        encoding_id=artifact_id,
        work_id=artifact_id,
        title="Bachbot figured bass realization",
        composer="Bachbot",
        source_format="internal",
        key_estimate=KeyEstimate(tonic=key_tonic, mode=mode),
        meter=meter,
        provenance=["Generated from figured bass under deterministic SATB constraints"],
    )
    voices = [
        Voice(voice_id="Soprano:1", section_id=section.section_id, part_name="Soprano", normalized_voice_name="Soprano"),
        Voice(voice_id="Alto:1", section_id=section.section_id, part_name="Alto", normalized_voice_name="Alto"),
        Voice(voice_id="Tenor:1", section_id=section.section_id, part_name="Tenor", normalized_voice_name="Tenor"),
        Voice(voice_id="Bass:1", section_id=section.section_id, part_name="Bass", normalized_voice_name="Bass"),
    ]
    return EventGraph(metadata=metadata, section=section, voices=voices, notes=notes)
