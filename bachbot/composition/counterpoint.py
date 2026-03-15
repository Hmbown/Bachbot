"""Species counterpoint exercise generator and validator.

Provides pedagogical tools for first through fifth species counterpoint
following Fux/Jeppesen traditions.  Includes built-in cantus firmi,
constrained generation, and rule-based validation with pedagogical feedback.

NOTE ON SCOPE: Species counterpoint is a pedagogical framework (Fux, 1725;
Jeppesen, 1939) — it does NOT model Bach's actual contrapuntal practice,
which is *free* counterpoint that routinely exceeds species constraints.
Use this module for teaching and exercises, not as a description of how
Bach composed.
"""

from __future__ import annotations

import random
from typing import Literal

from pydantic import Field

from bachbot.models.base import BachbotModel, TypedNote

# ---------------------------------------------------------------------------
# Interval constants (semitones mod 12)
# ---------------------------------------------------------------------------

CONSONANT_INTERVALS: frozenset[int] = frozenset({0, 3, 4, 7, 8, 9})
PERFECT_CONSONANCES: frozenset[int] = frozenset({0, 7})  # unison, P5 (octave via %12=0)

_INTERVAL_NAMES: dict[int, str] = {
    0: "unison/octave",
    1: "minor 2nd",
    2: "major 2nd",
    3: "minor 3rd",
    4: "major 3rd",
    5: "perfect 4th",
    6: "tritone",
    7: "perfect 5th",
    8: "minor 6th",
    9: "major 6th",
    10: "minor 7th",
    11: "major 7th",
}

_MELODIC_MAX_LEAP = 12  # P8

# Augmented/diminished melodic intervals to forbid (semitones)
_FORBIDDEN_MELODIC: frozenset[int] = frozenset({6})  # tritone


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class CounterpointViolation(BachbotModel):
    """A single rule violation with pedagogical explanation."""

    rule: str
    measure: int
    beat: float
    message: str


class CounterpointReport(BachbotModel):
    """Validation report for a species counterpoint exercise."""

    species: int
    violations: list[CounterpointViolation] = Field(default_factory=list)
    is_valid: bool = True
    score: float = 100.0


class CantusFirmus(BachbotModel):
    """A cantus firmus for counterpoint exercises."""

    name: str
    midi_notes: list[int]
    mode: str = "major"


# ---------------------------------------------------------------------------
# Built-in cantus firmi (10+)
# ---------------------------------------------------------------------------

# The primary Fux cantus firmus (D Dorian, from *Gradus ad Parnassum*, 1725)
# is the one melody reliably attributable to a specific source.  The remaining
# cantus firmi are pedagogical examples in the style of their named traditions
# but are not direct transcriptions from the original treatises.
CANTUS_FIRMI: list[CantusFirmus] = [
    # Verified: Fux's primary D-Dorian CF used throughout Gradus ad Parnassum
    CantusFirmus(name="Fux-1", midi_notes=[62, 65, 64, 62, 67, 65, 69, 67, 65, 64, 62], mode="dorian"),
    CantusFirmus(name="Fux-2", midi_notes=[62, 60, 62, 65, 64, 62, 64, 62, 60, 62], mode="dorian"),
    CantusFirmus(name="Fux-3", midi_notes=[64, 62, 60, 62, 64, 65, 67, 65, 64, 62, 64], mode="phrygian"),
    CantusFirmus(name="Fux-4", midi_notes=[65, 64, 62, 65, 67, 69, 67, 65, 64, 65], mode="lydian"),
    CantusFirmus(name="Fux-5", midi_notes=[67, 65, 64, 65, 67, 69, 67, 72, 71, 69, 67], mode="mixolydian"),
    CantusFirmus(name="Jeppesen-1", midi_notes=[60, 62, 64, 67, 65, 64, 62, 64, 62, 60], mode="major"),
    CantusFirmus(name="Jeppesen-2", midi_notes=[57, 60, 59, 57, 55, 57, 60, 59, 57], mode="minor"),
    CantusFirmus(name="Jeppesen-3", midi_notes=[60, 64, 62, 65, 64, 67, 65, 64, 62, 60], mode="major"),
    CantusFirmus(name="Salzer-1", midi_notes=[60, 62, 64, 60, 67, 65, 64, 62, 60], mode="major"),
    CantusFirmus(name="Salzer-2", midi_notes=[69, 67, 65, 67, 69, 72, 71, 69, 67, 69], mode="minor"),
    CantusFirmus(name="Schenker-1", midi_notes=[60, 65, 64, 62, 67, 65, 64, 62, 60], mode="major"),
    CantusFirmus(name="Schenker-2", midi_notes=[62, 64, 65, 62, 60, 62, 65, 64, 62], mode="dorian"),
]

_CF_LOOKUP: dict[str, CantusFirmus] = {cf.name: cf for cf in CANTUS_FIRMI}


def get_cantus_firmus(name: str) -> CantusFirmus:
    """Retrieve a built-in cantus firmus by name."""
    if name not in _CF_LOOKUP:
        raise ValueError(f"Unknown cantus firmus: {name!r}. Available: {list(_CF_LOOKUP)}")
    return _CF_LOOKUP[name]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _interval_class(midi_a: int, midi_b: int) -> int:
    """Absolute interval in semitones mod 12."""
    return abs(midi_a - midi_b) % 12


def _signed_interval(midi_a: int, midi_b: int) -> int:
    """Signed interval in semitones (b - a)."""
    return midi_b - midi_a


def _is_consonant(midi_a: int, midi_b: int) -> bool:
    return _interval_class(midi_a, midi_b) in CONSONANT_INTERVALS


def _is_perfect(midi_a: int, midi_b: int) -> bool:
    return _interval_class(midi_a, midi_b) in PERFECT_CONSONANCES


def _motion_type(
    prev_cf: int, curr_cf: int, prev_cp: int, curr_cp: int
) -> Literal["parallel", "similar", "contrary", "oblique"]:
    """Classify the relative motion between two voices."""
    d_cf = curr_cf - prev_cf
    d_cp = curr_cp - prev_cp
    if d_cf == 0 and d_cp == 0:
        return "oblique"
    if d_cf == 0 or d_cp == 0:
        return "oblique"
    if d_cf > 0 and d_cp > 0 or d_cf < 0 and d_cp < 0:
        if d_cf == d_cp:
            return "parallel"
        return "similar"
    return "contrary"


def _interval_name(midi_a: int, midi_b: int) -> str:
    ic = _interval_class(midi_a, midi_b)
    raw = abs(midi_a - midi_b)
    base = _INTERVAL_NAMES.get(ic, f"{ic} semitones")
    if raw > 12:
        return f"compound {base}"
    if raw == 12:
        return "octave"
    return base


# ---------------------------------------------------------------------------
# Validation: First Species
# ---------------------------------------------------------------------------

def _validate_first_species(
    cf: list[int], cp: list[int], position: str, violations: list[CounterpointViolation]
) -> None:
    n = len(cf)

    # Beginning interval
    begin_ic = _interval_class(cf[0], cp[0])
    if begin_ic not in {0, 7}:  # P1, P5, P8
        violations.append(CounterpointViolation(
            rule="begin_interval",
            measure=1,
            beat=1.0,
            message=f"Must begin on unison, perfect 5th, or octave; got {_interval_name(cf[0], cp[0])}.",
        ))

    # Ending interval
    end_ic = _interval_class(cf[-1], cp[-1])
    if end_ic not in {0}:  # P1 or P8 (both are 0 mod 12)
        violations.append(CounterpointViolation(
            rule="end_interval",
            measure=n,
            beat=1.0,
            message=f"Must end on unison or octave; got {_interval_name(cf[-1], cp[-1])}.",
        ))

    for i in range(n):
        m = i + 1
        # Consonance
        if not _is_consonant(cf[i], cp[i]):
            violations.append(CounterpointViolation(
                rule="dissonance_on_strong_beat",
                measure=m,
                beat=1.0,
                message=f"Dissonance ({_interval_name(cf[i], cp[i])}) at m.{m}. In first species, all intervals must be consonant.",
            ))

        # Voice crossing
        if position == "above" and cp[i] < cf[i]:
            violations.append(CounterpointViolation(
                rule="voice_crossing",
                measure=m,
                beat=1.0,
                message=f"Voice crossing at m.{m}: counterpoint (above) is below cantus.",
            ))
        elif position == "below" and cp[i] > cf[i]:
            violations.append(CounterpointViolation(
                rule="voice_crossing",
                measure=m,
                beat=1.0,
                message=f"Voice crossing at m.{m}: counterpoint (below) is above cantus.",
            ))

    # Parallel / direct 5ths and 8ves
    for i in range(1, n):
        m = i + 1
        motion = _motion_type(cf[i - 1], cf[i], cp[i - 1], cp[i])
        ic = _interval_class(cf[i], cp[i])

        if ic in PERFECT_CONSONANCES and motion == "parallel":
            name = "octaves/unisons" if ic == 0 else "fifths"
            violations.append(CounterpointViolation(
                rule=f"parallel_{name.replace('/', '_')}",
                measure=m,
                beat=1.0,
                message=f"Parallel {name} between m.{m - 1} and m.{m}. Move one voice by step while the other leaps.",
            ))

        if ic in PERFECT_CONSONANCES and motion == "similar":
            name = "octaves/unisons" if ic == 0 else "fifths"
            violations.append(CounterpointViolation(
                rule=f"direct_{name.replace('/', '_')}",
                measure=m,
                beat=1.0,
                message=f"Direct (hidden) {name} at m.{m}. Approach perfect consonances by contrary or oblique motion.",
            ))

    # Melodic checks on counterpoint line
    for i in range(1, n):
        m = i + 1
        leap = abs(cp[i] - cp[i - 1])
        if leap > _MELODIC_MAX_LEAP:
            violations.append(CounterpointViolation(
                rule="melodic_leap_too_large",
                measure=m,
                beat=1.0,
                message=f"Melodic leap of {leap} semitones at m.{m}; maximum is an octave (12).",
            ))
        if leap in _FORBIDDEN_MELODIC:
            violations.append(CounterpointViolation(
                rule="forbidden_melodic_interval",
                measure=m,
                beat=1.0,
                message=f"Tritone leap at m.{m}. Avoid augmented and diminished melodic intervals.",
            ))

    # Single climax
    max_pitch = max(cp)
    climax_count = cp.count(max_pitch)
    if climax_count > 1:
        violations.append(CounterpointViolation(
            rule="single_climax",
            measure=1,
            beat=1.0,
            message=f"Highest note ({max_pitch}) appears {climax_count} times; it should appear only once.",
        ))


# ---------------------------------------------------------------------------
# Validation: Second Species
# ---------------------------------------------------------------------------

def _validate_second_species(
    cf: list[int], cp: list[int], position: str, violations: list[CounterpointViolation]
) -> None:
    n_cf = len(cf)
    n_cp = len(cp)

    # Expected length: first half-rest + (n_cf - 1)*2 notes + 1 final whole
    # We treat cp as the sequence of sounding notes (no rests encoded).
    # Expected: 2*(n_cf - 1) + 1 = 2*n_cf - 1 notes if we include the final whole,
    # but simpler: just validate what we get.

    # Strong beat consonance (every other note starting from index 0 maps to cf beat)
    # cp[0] is on beat 2 of measure 1 (after half rest), with cf[0]
    # cp[1] is on beat 1 of measure 2, with cf[1], etc.
    # Simpler mapping: cp index i corresponds to cf index i // 2 for 2:1
    for i in range(n_cp):
        cf_idx = min(i // 2, n_cf - 1)
        m = cf_idx + 1
        is_strong = (i % 2 == 0)
        beat = 1.0 if is_strong else 3.0

        if is_strong:
            if not _is_consonant(cf[cf_idx], cp[i]):
                violations.append(CounterpointViolation(
                    rule="dissonance_on_strong_beat",
                    measure=m,
                    beat=beat,
                    message=f"Dissonance ({_interval_name(cf[cf_idx], cp[i])}) on strong beat at m.{m}. Strong beats must be consonant in second species.",
                ))
        else:
            # Weak beat: consonant or passing tone
            if not _is_consonant(cf[cf_idx], cp[i]):
                # Check if passing tone (stepwise between two consonances)
                is_passing = False
                if 0 < i < n_cp - 1:
                    step_in = abs(cp[i] - cp[i - 1]) <= 2
                    step_out = abs(cp[i + 1] - cp[i]) <= 2
                    same_dir = (cp[i] - cp[i - 1]) * (cp[i + 1] - cp[i]) > 0
                    if step_in and step_out and same_dir:
                        is_passing = True
                if not is_passing:
                    violations.append(CounterpointViolation(
                        rule="dissonance_not_passing",
                        measure=m,
                        beat=beat,
                        message=f"Dissonance ({_interval_name(cf[cf_idx], cp[i])}) on weak beat at m.{m} beat {beat} is not a valid passing tone.",
                    ))

    # Parallel 5ths/8ves on consecutive strong beats
    strong_indices = [i for i in range(n_cp) if i % 2 == 0]
    for j in range(1, len(strong_indices)):
        si_prev = strong_indices[j - 1]
        si_curr = strong_indices[j]
        cf_prev = min(si_prev // 2, n_cf - 1)
        cf_curr = min(si_curr // 2, n_cf - 1)
        m = cf_curr + 1

        ic_prev = _interval_class(cf[cf_prev], cp[si_prev])
        ic_curr = _interval_class(cf[cf_curr], cp[si_curr])
        if ic_prev in PERFECT_CONSONANCES and ic_curr == ic_prev:
            motion = _motion_type(cf[cf_prev], cf[cf_curr], cp[si_prev], cp[si_curr])
            if motion in ("parallel", "similar"):
                name = "octaves" if ic_curr == 0 else "fifths"
                violations.append(CounterpointViolation(
                    rule=f"parallel_{name}",
                    measure=m,
                    beat=1.0,
                    message=f"Parallel {name} on consecutive strong beats at m.{m - 1} and m.{m}.",
                ))


# ---------------------------------------------------------------------------
# Validation: Third Species
# ---------------------------------------------------------------------------

def _validate_third_species(
    cf: list[int], cp: list[int], position: str, violations: list[CounterpointViolation]
) -> None:
    n_cf = len(cf)
    n_cp = len(cp)

    for i in range(n_cp):
        cf_idx = min(i // 4, n_cf - 1)
        m = cf_idx + 1
        sub_beat = (i % 4) + 1
        beat = float(sub_beat)

        if sub_beat == 1:
            # First note of group must be consonant
            if not _is_consonant(cf[cf_idx], cp[i]):
                violations.append(CounterpointViolation(
                    rule="dissonance_on_first_beat",
                    measure=m,
                    beat=beat,
                    message=f"Dissonance ({_interval_name(cf[cf_idx], cp[i])}) on beat 1 of m.{m}. The first note of each group must be consonant in third species.",
                ))
        else:
            # Others: consonant, passing, or neighbor tone
            if not _is_consonant(cf[cf_idx], cp[i]):
                is_pt_or_nt = False
                if 0 < i < n_cp - 1:
                    step_in = abs(cp[i] - cp[i - 1]) <= 2
                    step_out = abs(cp[i + 1] - cp[i]) <= 2
                    if step_in and step_out:
                        is_pt_or_nt = True
                # Nota cambiata: leap from dissonance then step back
                if not is_pt_or_nt and i < n_cp - 2:
                    if abs(cp[i + 1] - cp[i]) > 2 and abs(cp[i + 2] - cp[i + 1]) <= 2:
                        is_pt_or_nt = True
                if not is_pt_or_nt:
                    violations.append(CounterpointViolation(
                        rule="dissonance_unresolved",
                        measure=m,
                        beat=beat,
                        message=f"Dissonance ({_interval_name(cf[cf_idx], cp[i])}) at m.{m} beat {beat} is neither passing, neighbor, nor cambiata.",
                    ))

    # Parallel 5ths/8ves on consecutive first beats
    first_beat_indices = [i for i in range(n_cp) if i % 4 == 0]
    for j in range(1, len(first_beat_indices)):
        fi_prev = first_beat_indices[j - 1]
        fi_curr = first_beat_indices[j]
        cf_prev = min(fi_prev // 4, n_cf - 1)
        cf_curr = min(fi_curr // 4, n_cf - 1)
        m = cf_curr + 1

        ic_prev = _interval_class(cf[cf_prev], cp[fi_prev])
        ic_curr = _interval_class(cf[cf_curr], cp[fi_curr])
        if ic_prev in PERFECT_CONSONANCES and ic_curr == ic_prev:
            motion = _motion_type(cf[cf_prev], cf[cf_curr], cp[fi_prev], cp[fi_curr])
            if motion in ("parallel", "similar"):
                name = "octaves" if ic_curr == 0 else "fifths"
                violations.append(CounterpointViolation(
                    rule=f"parallel_{name}",
                    measure=m,
                    beat=1.0,
                    message=f"Parallel {name} on consecutive first beats at m.{m - 1} and m.{m}.",
                ))


# ---------------------------------------------------------------------------
# Validation: Fourth Species
# ---------------------------------------------------------------------------

def _validate_fourth_species(
    cf: list[int], cp: list[int], position: str, violations: list[CounterpointViolation]
) -> None:
    n_cf = len(cf)
    n_cp = len(cp)

    # In fourth species, cp notes are syncopated: tied across barlines.
    # cp[i] sounds against cf[i // 2] (strong) and cf[min(i//2 + 1, n_cf-1)] (resolution).
    # Even indices = tied-over note (dissonance possible), odd = resolution (must step down if prev was dissonant).

    VALID_SUSPENSIONS_ABOVE = {7, 4, 9, 2}  # 7-6, 4-3, 9-8, 2-3 (intervals in semitones mod 12)
    # More practically: we check if dissonant on strong beat and resolves step down.

    for i in range(n_cp):
        cf_idx = min(i // 2, n_cf - 1)
        m = cf_idx + 1
        is_tied = (i % 2 == 0)
        beat = 1.0 if is_tied else 3.0

        if is_tied and not _is_consonant(cf[cf_idx], cp[i]):
            # Dissonant suspension: must resolve stepwise DOWN on next beat
            if i + 1 < n_cp:
                resolution_step = cp[i + 1] - cp[i]
                if resolution_step not in (-1, -2):
                    violations.append(CounterpointViolation(
                        rule="suspension_bad_resolution",
                        measure=m,
                        beat=beat,
                        message=f"Dissonant suspension ({_interval_name(cf[cf_idx], cp[i])}) at m.{m} must resolve stepwise down; got motion of {resolution_step} semitones.",
                    ))
            else:
                violations.append(CounterpointViolation(
                    rule="suspension_no_resolution",
                    measure=m,
                    beat=beat,
                    message=f"Dissonant suspension at m.{m} has no resolution.",
                ))


# ---------------------------------------------------------------------------
# Validation: Fifth Species (florid)
# ---------------------------------------------------------------------------

def _validate_fifth_species(
    cf: list[int], cp: list[int], position: str, violations: list[CounterpointViolation]
) -> None:
    """Fifth species combines all rules. We check basic consonance on strong beats
    and that dissonances are approached/left by step."""
    n_cf = len(cf)
    n_cp = len(cp)

    # Map cp notes to cf notes proportionally
    ratio = n_cp / max(n_cf, 1)

    for i in range(n_cp):
        cf_idx = min(int(i / ratio), n_cf - 1)
        m = cf_idx + 1
        # Determine if this is a "strong" position (first note against each cf note)
        is_first_against_cf = (i == 0) or (int(i / ratio) != int((i - 1) / ratio))

        if is_first_against_cf:
            if not _is_consonant(cf[cf_idx], cp[i]):
                # Allow suspension: if tied from previous and resolves down
                is_suspension = False
                if i > 0 and cp[i] == cp[i - 1]:
                    if i + 1 < n_cp and -2 <= (cp[i + 1] - cp[i]) <= -1:
                        is_suspension = True
                if not is_suspension:
                    violations.append(CounterpointViolation(
                        rule="dissonance_on_strong_beat",
                        measure=m,
                        beat=1.0,
                        message=f"Dissonance ({_interval_name(cf[cf_idx], cp[i])}) on strong position at m.{m}.",
                    ))
        else:
            if not _is_consonant(cf[cf_idx], cp[i]):
                # Must be passing or neighbor
                is_ok = False
                if 0 < i < n_cp - 1:
                    step_in = abs(cp[i] - cp[i - 1]) <= 2
                    step_out = abs(cp[i + 1] - cp[i]) <= 2
                    if step_in and step_out:
                        is_ok = True
                if not is_ok:
                    violations.append(CounterpointViolation(
                        rule="dissonance_unresolved",
                        measure=m,
                        beat=2.0,
                        message=f"Dissonance ({_interval_name(cf[cf_idx], cp[i])}) at m.{m} must be approached and left by step.",
                    ))


# ---------------------------------------------------------------------------
# Public validation entry point
# ---------------------------------------------------------------------------

_SPECIES_VALIDATORS = {
    1: _validate_first_species,
    2: _validate_second_species,
    3: _validate_third_species,
    4: _validate_fourth_species,
    5: _validate_fifth_species,
}


def validate_counterpoint(
    cantus_midi: list[int],
    student_midi: list[int],
    species: int,
    *,
    position: str = "above",
) -> CounterpointReport:
    """Validate a student counterpoint line against a cantus firmus.

    Parameters
    ----------
    cantus_midi : list[int]
        MIDI note numbers for the cantus firmus.
    student_midi : list[int]
        MIDI note numbers for the student's counterpoint.
    species : int
        Species number (1-5).
    position : str
        "above" or "below" — position of the counterpoint relative to the cantus.

    Returns
    -------
    CounterpointReport
        Validation results with violations and score.
    """
    if species not in _SPECIES_VALIDATORS:
        raise ValueError(f"Species must be 1-5, got {species}")

    violations: list[CounterpointViolation] = []
    _SPECIES_VALIDATORS[species](cantus_midi, student_midi, position, violations)

    penalty = len(violations) * 10.0
    score = max(0.0, 100.0 - penalty)
    return CounterpointReport(
        species=species,
        violations=violations,
        is_valid=len(violations) == 0,
        score=score,
    )


# ---------------------------------------------------------------------------
# Generation: constrained search
# ---------------------------------------------------------------------------

def _candidate_pitches(cf_note: int, position: str) -> list[int]:
    """Return candidate MIDI pitches consonant with cf_note."""
    candidates = []
    if position == "above":
        lo, hi = cf_note, cf_note + 19  # up to compound 6th
    else:
        lo, hi = cf_note - 19, cf_note
    for p in range(lo, hi + 1):
        if _is_consonant(cf_note, p):
            candidates.append(p)
    return candidates


def _score_transition(
    prev_cp: int,
    curr_cp: int,
    prev_cf: int,
    curr_cf: int,
    *,
    all_cp_so_far: list[int],
) -> float:
    """Score a candidate transition (lower is better)."""
    score = 0.0
    leap = abs(curr_cp - prev_cp)

    # Stepwise preference
    if leap <= 2:
        score -= 5.0
    elif leap <= 4:
        score -= 2.0
    elif leap > 7:
        score += 3.0
    if leap > _MELODIC_MAX_LEAP:
        score += 100.0  # effectively forbid

    # Tritone
    if leap in _FORBIDDEN_MELODIC:
        score += 50.0

    # Contrary motion preference
    motion = _motion_type(prev_cf, curr_cf, prev_cp, curr_cp)
    if motion == "contrary":
        score -= 4.0
    elif motion == "oblique":
        score -= 2.0

    # Penalize parallel perfect consonances heavily
    ic = _interval_class(curr_cf, curr_cp)
    if ic in PERFECT_CONSONANCES and motion == "parallel":
        score += 200.0
    if ic in PERFECT_CONSONANCES and motion == "similar":
        score += 100.0  # direct/hidden

    # Variety: penalize repeated pitches
    if curr_cp in all_cp_so_far:
        score += 1.0

    return score


def generate_counterpoint(
    cantus: CantusFirmus | list[int],
    species: int,
    *,
    position: str = "above",
    seed: int = 42,
) -> list[TypedNote]:
    """Generate a counterpoint line for the given cantus firmus.

    Parameters
    ----------
    cantus : CantusFirmus or list[int]
        The cantus firmus (model or raw MIDI list).
    species : int
        Species number (1-5).
    position : str
        "above" or "below".
    seed : int
        Random seed for determinism.

    Returns
    -------
    list[TypedNote]
        The generated counterpoint line.
    """
    if isinstance(cantus, CantusFirmus):
        cf = cantus.midi_notes
    else:
        cf = list(cantus)

    rng = random.Random(seed)

    if species == 1:
        cp_midi = _generate_first_species(cf, position, rng)
    elif species == 2:
        cp_midi = _generate_second_species(cf, position, rng)
    elif species == 3:
        cp_midi = _generate_third_species(cf, position, rng)
    elif species == 4:
        cp_midi = _generate_fourth_species(cf, position, rng)
    elif species == 5:
        cp_midi = _generate_fifth_species(cf, position, rng)
    else:
        raise ValueError(f"Species must be 1-5, got {species}")

    return _midi_to_typed_notes(cp_midi, species)


def _midi_to_typed_notes(midi_notes: list[int], species: int) -> list[TypedNote]:
    """Convert a list of MIDI pitches to TypedNote objects."""
    dur_map = {1: 4.0, 2: 2.0, 3: 1.0, 4: 2.0, 5: 1.0}
    duration = dur_map.get(species, 4.0)

    notes: list[TypedNote] = []
    offset = 0.0
    for i, midi in enumerate(midi_notes):
        # For species >= 2, compute measure from offset
        measure = int(offset // 4.0) + 1
        beat = (offset % 4.0) + 1.0
        notes.append(TypedNote(
            midi=midi,
            duration_quarters=duration,
            offset_quarters=offset,
            measure_number=measure,
            beat=beat,
            voice_id="Counterpoint:1",
        ))
        offset += duration
    return notes


# ---------------------------------------------------------------------------
# First species generation (1:1 greedy with lookahead)
# ---------------------------------------------------------------------------

def _generate_first_species(cf: list[int], position: str, rng: random.Random) -> list[int]:
    n = len(cf)
    result: list[int] = []

    # First note: P1, P5, or P8
    first_candidates = []
    for p in _candidate_pitches(cf[0], position):
        ic = _interval_class(cf[0], p)
        if ic in {0, 7}:  # P1, P5, P8
            first_candidates.append(p)
    if not first_candidates:
        first_candidates = _candidate_pitches(cf[0], position)
    result.append(rng.choice(first_candidates))

    # Compute last-note candidates once for lookahead
    last_note_options = []
    for p in _candidate_pitches(cf[-1], position):
        if _interval_class(cf[-1], p) == 0:
            last_note_options.append(p)
    if not last_note_options:
        last_note_options = [cf[-1] + (12 if position == "above" else -12)]

    # Middle notes: greedy with scoring
    for i in range(1, n - 1):
        candidates = _candidate_pitches(cf[i], position)
        if not candidates:
            # Fallback
            candidates = [cf[i] + (12 if position == "above" else -12)]
        scored = []
        for c in candidates:
            s = _score_transition(result[-1], c, cf[i - 1], cf[i], all_cp_so_far=result)
            # Penultimate note: lookahead to ensure good approach to final
            if i == n - 2:
                best_last_leap = min(abs(c - lp) for lp in last_note_options)
                if best_last_leap in _FORBIDDEN_MELODIC:
                    s += 50.0
                if best_last_leap > _MELODIC_MAX_LEAP:
                    s += 100.0
                if best_last_leap <= 2:
                    s -= 5.0  # stepwise approach bonus
            scored.append((s, c))
        scored.sort(key=lambda x: x[0])
        # Pick from top candidates with some randomness
        top_n = min(3, len(scored))
        best = scored[:top_n]
        result.append(rng.choice(best)[1])

    # Last note: P1 or P8, approach by step in contrary motion preferred
    last_candidates = []
    for p in _candidate_pitches(cf[-1], position):
        ic = _interval_class(cf[-1], p)
        if ic == 0:  # unison or octave
            last_candidates.append(p)
    if not last_candidates:
        last_candidates = [cf[-1] + (12 if position == "above" else -12)]

    # Score last-note candidates: prefer stepwise, contrary motion, no forbidden leaps
    def _last_score(p: int) -> float:
        s = 0.0
        leap = abs(p - result[-1])
        # Stepwise preference
        if leap <= 2:
            s -= 10.0
        elif leap <= 4:
            s -= 3.0
        # Penalize forbidden melodic intervals
        if leap in _FORBIDDEN_MELODIC:
            s += 100.0
        if leap > _MELODIC_MAX_LEAP:
            s += 200.0
        # Contrary motion to cf
        cf_dir = cf[-1] - cf[-2] if len(cf) >= 2 else 0
        cp_dir = p - result[-1]
        if cf_dir != 0 and cp_dir != 0 and (cf_dir > 0) != (cp_dir > 0):
            s -= 5.0  # contrary motion bonus
        # Penalize direct/hidden perfect consonance
        if len(cf) >= 2:
            motion = _motion_type(cf[-2], cf[-1], result[-1], p)
            if motion == "similar":
                s += 50.0
            elif motion == "parallel":
                s += 100.0
        return s

    last_candidates.sort(key=_last_score)
    result.append(last_candidates[0])

    return result


# ---------------------------------------------------------------------------
# Second species generation (2:1)
# ---------------------------------------------------------------------------

def _generate_second_species(cf: list[int], position: str, rng: random.Random) -> list[int]:
    n = len(cf)
    result: list[int] = []

    # For each CF note, generate 2 CP notes (strong + weak), except last = 1 whole note
    for i in range(n):
        if i == n - 1:
            # Final: single consonant whole note
            candidates = [p for p in _candidate_pitches(cf[i], position) if _interval_class(cf[i], p) == 0]
            if not candidates:
                candidates = _candidate_pitches(cf[i], position)
            if result:
                best = min(candidates, key=lambda p: abs(p - result[-1]))
                result.append(best)
            else:
                result.append(rng.choice(candidates))
            break

        # Strong beat: consonant
        candidates = _candidate_pitches(cf[i], position)
        if i == 0:
            # Begin with consonance (after half-rest conceptually, but we just pick first note)
            result.append(rng.choice(candidates) if candidates else cf[i] + 12)
        else:
            if result:
                scored = [(
                    _score_transition(result[-1], c, cf[max(0, i - 1)], cf[i], all_cp_so_far=result),
                    c,
                ) for c in candidates]
                scored.sort(key=lambda x: x[0])
                top = scored[:min(3, len(scored))]
                result.append(rng.choice(top)[1])
            else:
                result.append(rng.choice(candidates))

        # Weak beat: consonant or passing tone
        weak_candidates = []
        next_cf = cf[min(i + 1, n - 1)]
        strong_note = result[-1]

        # Try consonant weak-beat pitches first
        for p in _candidate_pitches(cf[i], position):
            if abs(p - strong_note) <= 4:  # reasonable step
                weak_candidates.append(p)

        # Add passing tone candidates (stepwise from strong, continuing direction)
        if i + 1 < n:
            next_strong_candidates = _candidate_pitches(next_cf, position)
            for ns in next_strong_candidates[:5]:
                direction = 1 if ns > strong_note else -1
                pt = strong_note + direction * 2  # whole step
                if abs(pt - strong_note) <= 2 and abs(ns - pt) <= 2:
                    weak_candidates.append(pt)
                pt2 = strong_note + direction * 1  # half step
                if abs(ns - pt2) <= 2:
                    weak_candidates.append(pt2)

        if not weak_candidates:
            weak_candidates = [strong_note + (2 if position == "above" else -2)]

        # Deduplicate and pick
        weak_candidates = list(set(weak_candidates))
        # Prefer consonant
        consonant_weak = [w for w in weak_candidates if _is_consonant(cf[i], w)]
        if consonant_weak:
            result.append(rng.choice(consonant_weak))
        else:
            result.append(rng.choice(weak_candidates))

    return result


# ---------------------------------------------------------------------------
# Third species generation (4:1)
# ---------------------------------------------------------------------------

def _generate_third_species(cf: list[int], position: str, rng: random.Random) -> list[int]:
    n = len(cf)
    result: list[int] = []

    for i in range(n):
        if i == n - 1:
            # Final whole note
            candidates = [p for p in _candidate_pitches(cf[i], position) if _interval_class(cf[i], p) == 0]
            if not candidates:
                candidates = _candidate_pitches(cf[i], position)
            if result:
                result.append(min(candidates, key=lambda p: abs(p - result[-1])))
            else:
                result.append(rng.choice(candidates))
            break

        # Beat 1: consonant
        candidates = _candidate_pitches(cf[i], position)
        if result:
            scored = [(
                _score_transition(result[-1], c, cf[max(0, i - 1)], cf[i], all_cp_so_far=result),
                c,
            ) for c in candidates]
            scored.sort(key=lambda x: x[0])
            top = scored[:min(3, len(scored))]
            result.append(rng.choice(top)[1])
        else:
            result.append(rng.choice(candidates))

        # Beats 2-4: stepwise fill (passing/neighbor tones)
        start = result[-1]
        # Target: next beat 1
        if i + 1 < n:
            next_consonant = _candidate_pitches(cf[i + 1], position)
            if next_consonant:
                target = min(next_consonant, key=lambda p: abs(p - start))
            else:
                target = start
        else:
            target = start

        # Fill 3 notes stepwise from start toward target
        diff = target - start
        if abs(diff) >= 3:
            step = 1 if diff > 0 else -1
            for j in range(3):
                next_p = result[-1] + step * rng.choice([1, 2])
                result.append(next_p)
        else:
            # Neighbor tone pattern
            step = rng.choice([1, 2])
            direction = 1 if rng.random() < 0.5 else -1
            result.append(start + direction * step)
            result.append(start)
            result.append(start - direction * step if diff == 0 else start + (1 if diff > 0 else -1))

    return result


# ---------------------------------------------------------------------------
# Fourth species generation (syncopated)
# ---------------------------------------------------------------------------

def _generate_fourth_species(cf: list[int], position: str, rng: random.Random) -> list[int]:
    n = len(cf)
    result: list[int] = []

    # Standard suspensions resolve down: 7-6, 4-3, 9-8
    for i in range(n):
        if i == n - 1:
            candidates = [p for p in _candidate_pitches(cf[i], position) if _interval_class(cf[i], p) == 0]
            if not candidates:
                candidates = _candidate_pitches(cf[i], position)
            if result:
                result.append(min(candidates, key=lambda p: abs(p - result[-1])))
            else:
                result.append(rng.choice(candidates))
            break

        # Tied note (sounds on strong beat of current measure)
        if i == 0:
            candidates = _candidate_pitches(cf[i], position)
            result.append(rng.choice(candidates))
        else:
            # Tie from previous: reuse last pitch (the suspension)
            result.append(result[-1])

        # Resolution / preparation for next suspension
        # If the tied note is dissonant with CF, MUST resolve stepwise down.
        # Otherwise, pick a consonant note nearby (preferring stepwise).
        prev = result[-1]
        is_dissonant = not _is_consonant(cf[i], prev)
        consonant_candidates = _candidate_pitches(cf[i], position)

        if is_dissonant:
            # Must resolve stepwise down (-1 or -2 semitones)
            step_down = [p for p in consonant_candidates if prev - p in (1, 2)]
            if step_down:
                result.append(rng.choice(step_down))
            else:
                # Force resolution down even if not perfectly consonant
                result.append(prev - 1)
        else:
            # Consonant syncopation: pick nearby consonant note
            step_down = [p for p in consonant_candidates if 0 < prev - p <= 2]
            step_up = [p for p in consonant_candidates if 0 < p - prev <= 2]
            nearby = step_down + step_up
            if nearby:
                result.append(rng.choice(nearby))
            elif consonant_candidates:
                result.append(min(consonant_candidates, key=lambda p: abs(p - prev)))
            else:
                result.append(prev - 1)

    return result


# ---------------------------------------------------------------------------
# Fifth species generation (florid — mixed rhythms)
# ---------------------------------------------------------------------------

def _generate_fifth_species(cf: list[int], position: str, rng: random.Random) -> list[int]:
    """Generate florid counterpoint: mix of whole, half, and quarter notes.

    For simplicity, we generate a variable number of notes per CF note,
    mixing species 1-4 patterns.
    """
    n = len(cf)
    result: list[int] = []

    for i in range(n):
        if i == n - 1:
            # Final: single note
            candidates = [p for p in _candidate_pitches(cf[i], position) if _interval_class(cf[i], p) == 0]
            if not candidates:
                candidates = _candidate_pitches(cf[i], position)
            if result:
                result.append(min(candidates, key=lambda p: abs(p - result[-1])))
            else:
                result.append(rng.choice(candidates))
            break

        # Choose rhythm pattern for this measure
        pattern = rng.choice(["whole", "half", "quarter", "suspension"])

        if pattern == "whole":
            # 1 note (species 1 style)
            candidates = _candidate_pitches(cf[i], position)
            if result:
                scored = [(
                    _score_transition(result[-1], c, cf[max(0, i - 1)], cf[i], all_cp_so_far=result),
                    c,
                ) for c in candidates]
                scored.sort(key=lambda x: x[0])
                result.append(scored[0][1] if scored else rng.choice(candidates))
            else:
                result.append(rng.choice(candidates))

        elif pattern == "half":
            # 2 notes (species 2 style)
            candidates = _candidate_pitches(cf[i], position)
            if result:
                scored = [(
                    _score_transition(result[-1], c, cf[max(0, i - 1)], cf[i], all_cp_so_far=result),
                    c,
                ) for c in candidates]
                scored.sort(key=lambda x: x[0])
                result.append(scored[0][1] if scored else rng.choice(candidates))
            else:
                result.append(rng.choice(candidates))
            # Weak beat
            step = rng.choice([-2, -1, 1, 2])
            result.append(result[-1] + step)

        elif pattern == "quarter":
            # 4 notes (species 3 style)
            candidates = _candidate_pitches(cf[i], position)
            if result:
                scored = [(
                    _score_transition(result[-1], c, cf[max(0, i - 1)], cf[i], all_cp_so_far=result),
                    c,
                ) for c in candidates]
                scored.sort(key=lambda x: x[0])
                result.append(scored[0][1] if scored else rng.choice(candidates))
            else:
                result.append(rng.choice(candidates))
            base = result[-1]
            for _j in range(3):
                step = rng.choice([-2, -1, 1, 2])
                result.append(result[-1] + step)

        elif pattern == "suspension":
            # 2 notes, first tied from previous (species 4 style)
            if result:
                result.append(result[-1])  # tie
            else:
                candidates = _candidate_pitches(cf[i], position)
                result.append(rng.choice(candidates))
            # Resolution
            consonant = _candidate_pitches(cf[i], position)
            prev = result[-1]
            step_down = [p for p in consonant if 0 < prev - p <= 2]
            if step_down:
                result.append(rng.choice(step_down))
            elif consonant:
                result.append(min(consonant, key=lambda p: abs(p - prev)))
            else:
                result.append(prev - 1)

    return result


def _fifth_species_to_typed_notes(midi_notes: list[int], cf_len: int) -> list[TypedNote]:
    """For fifth species, assign variable durations. This is handled by _midi_to_typed_notes
    with quarter-note duration, which is a simplification."""
    return _midi_to_typed_notes(midi_notes, 5)
