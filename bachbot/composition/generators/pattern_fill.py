from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations

from bachbot.composition.state import CompositionState
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.encodings.musicxml_io import midi_to_note_name
from bachbot.models.base import TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice

NOTE_TO_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}

# All chord intervals as tuples (root is first element) — matches roman_candidates.py
CHORD_INTERVALS = {
    # Major key triads
    "I": (0, 4, 7), "ii": (2, 5, 9), "iii": (4, 7, 11),
    "IV": (5, 9, 0), "V": (7, 11, 2), "vi": (9, 0, 4), "vii°": (11, 2, 5),
    # Minor key triads
    "i": (0, 3, 7), "ii°": (2, 5, 8), "III": (3, 7, 10),
    "iv": (5, 8, 0), "VI": (8, 0, 3), "VII": (10, 2, 5),
    # Major key seventh chords
    "V7": (7, 11, 2, 5), "viiø7": (11, 2, 5, 9), "ii7": (2, 5, 9, 0),
    "IV7": (5, 9, 0, 4), "vi7": (9, 0, 4, 7),
    # Minor key seventh chords
    "viio7": (11, 2, 5, 8), "iiø7": (2, 5, 8, 0),
    "iv7": (5, 8, 0, 3), "VI7": (8, 0, 3, 7),
    # Secondary dominants (intervals relative to tonic)
    "V/ii": (9, 1, 4), "V/V": (2, 6, 9), "V/vi": (4, 8, 11),
    "V7/V": (2, 6, 9, 0), "V7/IV": (0, 4, 7, 10), "V7/ii": (9, 1, 4, 7), "V7/vi": (4, 8, 11, 2),
    "viio7/V": (6, 9, 0, 3), "viio7/ii": (1, 4, 7, 10), "viio7/vi": (8, 11, 2, 5),
}
ALL_CHORDS = {k: set(v) for k, v in CHORD_INTERVALS.items()}

# Degree roots for dynamic secondary dominant resolution
_DEGREE_ROOTS = {
    "I": 0, "ii": 2, "iii": 4, "IV": 5, "V": 7, "vi": 9, "vii°": 11,
    "i": 0, "ii°": 2, "III": 3, "iv": 5, "VI": 8, "VII": 10,
}


def _resolve_secondary_dominant(label: str) -> tuple[int, ...] | None:
    """Resolve a secondary dominant label (e.g., 'V/V') to intervals from tonic.

    Returns None if the label isn't a recognizable secondary dominant pattern.
    """
    if "/" not in label:
        return None
    quality, target = label.split("/", 1)
    target_root = _DEGREE_ROOTS.get(target)
    if target_root is None:
        return None
    dom_root = (target_root + 7) % 12
    if quality == "V":
        return (dom_root, (dom_root + 4) % 12, (dom_root + 7) % 12)
    if quality == "V7":
        return (dom_root, (dom_root + 4) % 12, (dom_root + 7) % 12, (dom_root + 10) % 12)
    if quality == "viio7":
        lt = (target_root + 11) % 12
        return (lt, (lt + 3) % 12, (lt + 6) % 12, (lt + 9) % 12)
    return None

RANGES = {"Soprano": (60, 81), "Alto": (55, 74), "Tenor": (48, 69), "Bass": (36, 64)}
PERFECT_INTERVALS = {0, 7}
DEFAULT_DEGREE_CHORD_MAJOR = {"1": "I", "2": "ii", "3": "iii", "4": "IV", "5": "V", "6": "vi", "7": "vii°"}
DEFAULT_DEGREE_CHORD_MINOR = {"1": "i", "2": "ii°", "3": "III", "4": "iv", "5": "V", "6": "VI", "7": "VII"}
_SPACING_LIMITS = [("Soprano:1", "Alto:1", 12), ("Alto:1", "Tenor:1", 12), ("Tenor:1", "Bass:1", 19)]
_SUSPENSION_VOICE_MAP = {
    "S": "Soprano:1",
    "A": "Alto:1",
    "T": "Tenor:1",
    "B": "Bass:1",
    "Soprano:1": "Soprano:1",
    "Alto:1": "Alto:1",
    "Tenor:1": "Tenor:1",
    "Bass:1": "Bass:1",
}


@dataclass(frozen=True)
class HarmonizationStep:
    chord_label: str
    soprano_midi: int
    alto_midi: int
    tenor_midi: int
    bass_midi: int


def _degree(midi: int, tonic: str) -> str:
    relative = (midi % 12 - NOTE_TO_PC[tonic]) % 12
    return {0: "1", 2: "2", 4: "3", 5: "4", 7: "5", 9: "6", 11: "7"}.get(relative, "1")


def _candidate_values(chord_pcs: set[int], low: int, high: int, preferred: int, *, ceiling: int | None = None, floor: int | None = None) -> list[int]:
    candidates = [
        midi
        for midi in range(low, high + 1)
        if midi % 12 in chord_pcs and (ceiling is None or midi < ceiling) and (floor is None or midi > floor)
    ]
    return sorted(candidates, key=lambda midi: (abs(midi - preferred), midi))


def _motion(left: int, right: int) -> int:
    if right > left:
        return 1
    if right < left:
        return -1
    return 0


_OUTER_VOICES = frozenset({"Soprano:1", "Bass:1"})


def _has_forbidden_parallel(previous: dict[str, int], current: dict[str, int]) -> bool:
    if not previous:
        return False
    shared = set(previous) & set(current)
    for upper, lower in combinations(shared, 2):
        previous_interval = abs(previous[upper] - previous[lower]) % 12
        current_interval = abs(current[upper] - current[lower]) % 12
        upper_motion = _motion(previous[upper], current[upper])
        lower_motion = _motion(previous[lower], current[lower])
        if previous_interval in PERFECT_INTERVALS and current_interval in PERFECT_INTERVALS and upper_motion == lower_motion != 0:
            if previous_interval == current_interval:
                return True  # True parallel 5ths/8ves — always forbidden
            if {upper, lower} == _OUTER_VOICES:
                return True  # Direct perfect interval — forbidden in outer voices only
    return False


def _fallback(candidates: list[int], default: int) -> int:
    return candidates[0] if candidates else default


def _extract_degree_chord_map(bundle: dict, tonic: str, mode: str = "major") -> dict[str, str]:
    """Build a soprano-degree -> chord mapping from bundle harmonic events.

    Starts from musically-sound defaults and upgrades triads to seventh chords
    when the bundle evidence supports it (e.g., V -> V7 when V7 is more common).
    """
    harmony = bundle.get("deterministic_findings", {}).get("harmony", [])
    defaults = DEFAULT_DEGREE_CHORD_MINOR if mode == "minor" else DEFAULT_DEGREE_CHORD_MAJOR
    if not harmony:
        return defaults.copy()

    # Count chord label frequencies across all harmonic events
    chord_counts: Counter = Counter()
    for event in harmony:
        candidates = event.get("roman_numeral_candidate_set", [])
        if candidates and candidates[0] in ALL_CHORDS:
            chord_counts[candidates[0]] += 1

    if not chord_counts:
        return defaults.copy()

    result = defaults.copy()

    # Upgrade triads to seventh chords when the bundle shows them more often
    _SEVENTH_UPGRADES = {
        "V": "V7", "vii°": "viiø7", "ii": "ii7", "IV": "IV7", "vi": "vi7",
        "iv": "iv7", "VI": "VI7", "ii°": "iiø7",
    }
    for deg, base_chord in list(result.items()):
        seventh = _SEVENTH_UPGRADES.get(base_chord)
        if seventh and chord_counts.get(seventh, 0) > chord_counts.get(base_chord, 0):
            result[deg] = seventh

    return result


def _extract_onset_chord_plan(bundle: dict) -> list[tuple[float, str]]:
    """Build onset → chord_label pairs from bundle harmonic events, sorted by onset."""
    harmony = bundle.get("deterministic_findings", {}).get("harmony", [])
    pairs: list[tuple[float, str]] = []
    for event in harmony:
        onset = event.get("onset")
        candidates = event.get("roman_numeral_candidate_set", [])
        if onset is not None and candidates:
            label = candidates[0]
            if label in ALL_CHORDS or _resolve_secondary_dominant(label) is not None:
                pairs.append((float(onset), label))
    pairs.sort()
    return pairs


def _lookup_chord_at_onset(plan: list[tuple[float, str]], onset: float) -> str | None:
    """Find the chord active at a given onset (latest entry ≤ onset).

    When a secondary dominant appears within 1 beat before the onset, it takes
    priority over a subsequent diatonic entry. This prevents sub-beat secondary
    dominants from being eclipsed by diatonic chords at the downbeat.
    """
    if not plan:
        return None
    result: str | None = None
    sec_dom: str | None = None
    for plan_onset, chord in plan:
        if plan_onset > onset + 1e-6:
            break
        result = chord
        if "/" in chord and onset - plan_onset < 1.0:
            sec_dom = chord
    return sec_dom or result


def _extract_local_key_map(bundle: dict) -> dict[int, str]:
    """Map measure numbers to local key tonic from bundle harmony events."""
    harmony = bundle.get("deterministic_findings", {}).get("harmony", [])
    if not harmony:
        return {}
    measure_keys: dict[int, Counter] = {}
    for event in harmony:
        ref = event.get("ref_id", "")
        local_key = event.get("local_key", "")
        if not local_key or "m" not in ref:
            continue
        measure_str = ref.rsplit("m", 1)[-1]
        if not measure_str.isdigit():
            continue
        measure_keys.setdefault(int(measure_str), Counter())[local_key.split()[0]] += 1
    return {m: counts.most_common(1)[0][0] for m, counts in measure_keys.items() if counts}


def _extract_cadence_plan(bundle: dict) -> list[dict]:
    """Extract cadence types and phrase boundary measures from bundle."""
    cadences = bundle.get("deterministic_findings", {}).get("cadences", [])
    phrase_endings = bundle.get("deterministic_findings", {}).get("phrase_endings", [])
    plan = []
    for pe in phrase_endings:
        cad_type = pe.get("type", "IAC")
        plan.append({"measure": pe.get("measure"), "cadence_type": cad_type})
    if not plan:
        for cad in cadences:
            ref = cad.get("ref_id", "")
            measure_str = ref.rsplit("m", 1)[-1] if "m" in ref else None
            if measure_str and measure_str.isdigit():
                plan.append({"measure": int(measure_str), "cadence_type": cad.get("cadence_type", "IAC")})
    return plan


def _extract_suspension_plan(bundle: dict) -> set[tuple[int, str]]:
    """Extract (measure, voice_id) suspension targets from the bundle."""
    details = (
        bundle.get("deterministic_findings", {})
        .get("voice_leading", {})
        .get("counterpoint", {})
        .get("suspension_details", [])
    )
    plan: set[tuple[int, str]] = set()
    for item in details:
        measure = item.get("measure")
        voice = _SUSPENSION_VOICE_MAP.get(str(item.get("voice", "")))
        if isinstance(measure, int) and voice is not None:
            plan.add((measure, voice))
    return plan


def _generate_beat_voicings(
    soprano_midi: int,
    chord_pcs: set[int],
    bass_pc_options: list[int],
    targets: dict[str, int],
    max_per_beat: int = 80,
) -> list[tuple[int, int, int]]:
    """Generate candidate (alto, tenor, bass) tuples for one beat.

    Candidates respect range and spacing constraints. Capped to *max_per_beat*
    closest to *targets* to keep Viterbi tractable.
    """
    voicings: list[tuple[int, int, int]] = []
    t_alto = targets.get("Alto:1", 64)
    t_tenor = targets.get("Tenor:1", 55)
    t_bass = targets.get("Bass:1", 43)
    for bass_pc in bass_pc_options:
        alto_cands = _candidate_values(
            chord_pcs, *RANGES["Alto"], t_alto,
            ceiling=soprano_midi, floor=soprano_midi - 13,
        )
        for alto in alto_cands:
            tenor_cands = _candidate_values(
                chord_pcs, *RANGES["Tenor"], t_tenor,
                ceiling=alto, floor=alto - 13,
            )
            for tenor in tenor_cands:
                bass_cands = _candidate_values(
                    {bass_pc}, *RANGES["Bass"], t_bass,
                    ceiling=tenor, floor=tenor - 20,
                )
                for bass in bass_cands:
                    voicings.append((alto, tenor, bass))
    if len(voicings) > max_per_beat:
        voicings.sort(key=lambda v: abs(v[0] - t_alto) + abs(v[1] - t_tenor) + abs(v[2] - t_bass))
        voicings = voicings[:max_per_beat]
    return voicings


def _viterbi_voicings(
    melody: list[TypedNote],
    beat_data: list[tuple[set[int], list[int]]],
    initial_targets: dict[str, int],
) -> list[dict[str, int]] | None:
    """Find minimum-cost voicing sequence via Viterbi DP.

    Each beat has candidate voicings (soprano fixed from melody). The algorithm
    finds the path through the trellis that minimizes total voice motion while
    heavily penalizing parallel 5ths/8ves.

    Returns None if any beat has zero candidates (caller should use greedy fallback).
    """
    n = len(melody)
    if n == 0:
        return []

    PARALLEL_PENALTY = 1000.0
    INF = float("inf")

    # Pre-generate candidates per beat, sliding targets toward closest candidate
    targets = dict(initial_targets)
    candidates: list[list[tuple[int, int, int]]] = []
    for i in range(n):
        chord_pcs, bass_opts = beat_data[i]
        voicings = _generate_beat_voicings(melody[i].midi, chord_pcs, bass_opts, targets)
        if not voicings:
            return None
        candidates.append(voicings)
        targets = {"Alto:1": voicings[0][0], "Tenor:1": voicings[0][1], "Bass:1": voicings[0][2]}

    # DP arrays — dp_prev[j] = cost to reach candidate j at previous beat
    init_a = initial_targets.get("Alto:1", 64)
    init_t = initial_targets.get("Tenor:1", 55)
    init_b = initial_targets.get("Bass:1", 43)

    dp_prev = [
        abs(a - init_a) + abs(t - init_t) + abs(b - init_b)
        for a, t, b in candidates[0]
    ]
    # Backpointers: bp[beat][j] = predecessor index at beat-1
    bp: list[list[int]] = [[-1] * len(candidates[0])]

    for beat in range(1, n):
        curr = candidates[beat]
        prev = candidates[beat - 1]
        s_prev = melody[beat - 1].midi
        s_curr = melody[beat].midi
        dp_curr = [INF] * len(curr)
        bp_curr = [-1] * len(curr)

        for j, (a_c, t_c, b_c) in enumerate(curr):
            curr_v = {"Soprano:1": s_curr, "Alto:1": a_c, "Tenor:1": t_c, "Bass:1": b_c}
            best = INF
            best_k = -1
            for k, (a_p, t_p, b_p) in enumerate(prev):
                if dp_prev[k] >= INF:
                    continue
                prev_v = {"Soprano:1": s_prev, "Alto:1": a_p, "Tenor:1": t_p, "Bass:1": b_p}
                motion = abs(a_c - a_p) + abs(t_c - t_p) + abs(b_c - b_p)
                penalty = PARALLEL_PENALTY if _has_forbidden_parallel(prev_v, curr_v) else 0.0
                total = dp_prev[k] + motion + penalty
                if total < best:
                    best = total
                    best_k = k
            dp_curr[j] = best
            bp_curr[j] = best_k

        dp_prev = dp_curr
        bp.append(bp_curr)

    # Backtrack from best final state
    if all(c >= INF for c in dp_prev):
        return None
    best_final = min(range(len(dp_prev)), key=lambda i: dp_prev[i])
    path = [best_final]
    for beat in range(n - 1, 0, -1):
        path.append(bp[beat][path[-1]])
    path.reverse()

    return [
        {"Soprano:1": melody[beat].midi, "Alto:1": candidates[beat][path[beat]][0],
         "Tenor:1": candidates[beat][path[beat]][1], "Bass:1": candidates[beat][path[beat]][2]}
        for beat in range(n)
    ]


# ── Two-phase composition: outer voices first, then inner ──


def _generate_bass_candidates(
    bass_pc_options: list[int],
    target_bass: int,
    tenor_ceiling: int = 69,
    max_candidates: int = 20,
) -> list[int]:
    """Generate bass MIDI candidates sorted by proximity to target."""
    low, high = RANGES["Bass"]
    cands = []
    for pc in bass_pc_options:
        for midi in range(low, high + 1):
            if midi % 12 == pc and midi < tenor_ceiling:
                cands.append(midi)
    cands.sort(key=lambda m: (abs(m - target_bass), m))
    return cands[:max_candidates]


def _bass_is_root(bass_pc: int, chord_intervals: tuple[int, ...], tonic_pc: int) -> bool:
    """Check if the bass pitch class is the chord root."""
    root_pc = (tonic_pc + chord_intervals[0]) % 12
    return bass_pc == root_pc


def _is_strong_beat(beat: float) -> bool:
    """Beat 1 and 3 are strong in common time (beats are 1-based).

    Only exact integer beats qualify — sub-beats (e.g., 1.5, 2.5) are weak.
    """
    return abs(beat - round(beat)) < 1e-6 and round(beat) in (1, 3)


def _viterbi_bass_line(
    melody: list[TypedNote],
    beat_data: list[tuple[set[int], list[int]]],
    beat_chord_labels: list[str],
    initial_bass: int = 43,
    tonic_pcs: list[int] | None = None,
) -> list[int] | None:
    """Find optimal bass line via 2-voice (soprano+bass) Viterbi.

    Scoring criteria:
    - Melodic smoothness: prefer stepwise, penalize large leaps
    - Contrary motion with soprano: bonus when bass moves opposite to soprano
    - Root position on strong beats: bonus for root in bass
    - Inversions on weak beats: reduced root-position preference
    - Parallel 5th/8ve avoidance: heavy penalty

    *tonic_pcs* supplies a per-beat tonic pitch class (accounting for local key
    modulation).  When omitted, defaults to 0 for every beat.
    """
    n = len(melody)
    if n == 0:
        return []

    if tonic_pcs is None:
        tonic_pcs = [0] * n

    PARALLEL_PENALTY = 1000.0
    CONTRARY_BONUS = -3.0
    ROOT_STRONG_BONUS = -15.0
    ROOT_WEAK_BONUS = -1.0
    NON_ROOT_STRONG_PENALTY = 5.0  # penalize inversions on strong beats
    LEAP_PENALTY_FACTOR = 0.4  # extra cost per semitone beyond stepwise
    INF = float("inf")

    # Generate bass candidates per beat
    candidates: list[list[int]] = []
    target = initial_bass
    for i in range(n):
        _, bass_opts = beat_data[i]
        cands = _generate_bass_candidates(bass_opts, target, tenor_ceiling=melody[i].midi - 5 if melody[i].midi else 69)
        if not cands:
            return None
        candidates.append(cands)
        target = cands[0]

    # DP: dp_prev[j] = cost to reach bass candidate j at previous beat
    dp_prev = [float(abs(b - initial_bass)) for b in candidates[0]]
    # Add position bonus for first beat — respect _is_strong_beat
    first_is_strong = _is_strong_beat(melody[0].beat) if n > 0 else False
    for j, bass in enumerate(candidates[0]):
        chord_label = beat_chord_labels[0]
        chord_ints = CHORD_INTERVALS.get(chord_label) or _resolve_secondary_dominant(chord_label) or (0,)
        is_root = _bass_is_root(bass % 12, chord_ints, tonic_pcs[0])
        if is_root:
            dp_prev[j] += ROOT_STRONG_BONUS if first_is_strong else ROOT_WEAK_BONUS
        elif first_is_strong:
            dp_prev[j] += NON_ROOT_STRONG_PENALTY

    bp: list[list[int]] = [[-1] * len(candidates[0])]

    for beat in range(1, n):
        curr = candidates[beat]
        prev = candidates[beat - 1]
        s_prev = melody[beat - 1].midi
        s_curr = melody[beat].midi
        soprano_direction = _motion(s_prev, s_curr) if s_prev and s_curr else 0
        is_strong = _is_strong_beat(melody[beat].beat)
        beat_tonic = tonic_pcs[beat]

        chord_label = beat_chord_labels[beat]
        chord_ints = CHORD_INTERVALS.get(chord_label) or _resolve_secondary_dominant(chord_label) or (0,)

        dp_curr = [INF] * len(curr)
        bp_curr = [-1] * len(curr)

        for j, bass_c in enumerate(curr):
            # Position score: root vs inversion
            is_root = _bass_is_root(bass_c % 12, chord_ints, beat_tonic)
            if is_root:
                position_bonus = ROOT_STRONG_BONUS if is_strong else ROOT_WEAK_BONUS
            else:
                position_bonus = NON_ROOT_STRONG_PENALTY if is_strong else 0.0

            best = INF
            best_k = -1
            for k, bass_p in enumerate(prev):
                if dp_prev[k] >= INF:
                    continue
                interval = abs(bass_c - bass_p)
                # Stepwise (0-2 semitones) is cheap, leaps are progressively expensive
                motion_cost = interval + max(0, interval - 2) * LEAP_PENALTY_FACTOR

                # Contrary motion bonus
                bass_direction = _motion(bass_p, bass_c)
                contrary = CONTRARY_BONUS if soprano_direction != 0 and bass_direction == -soprano_direction else 0.0

                # Parallel check (outer voices only)
                prev_v = {"Soprano:1": s_prev, "Bass:1": bass_p}
                curr_v = {"Soprano:1": s_curr, "Bass:1": bass_c}
                penalty = PARALLEL_PENALTY if _has_forbidden_parallel(prev_v, curr_v) else 0.0

                total = dp_prev[k] + motion_cost + contrary + penalty + position_bonus
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

    return [candidates[beat][path[beat]] for beat in range(n)]


def _generate_inner_voicings(
    soprano_midi: int,
    bass_midi: int,
    chord_pcs: set[int],
    targets: dict[str, int],
    max_per_beat: int = 80,
) -> list[tuple[int, int]]:
    """Generate (alto, tenor) candidates given fixed soprano and bass."""
    voicings: list[tuple[int, int]] = []
    t_alto = targets.get("Alto:1", 64)
    t_tenor = targets.get("Tenor:1", 55)
    alto_cands = _candidate_values(
        chord_pcs, *RANGES["Alto"], t_alto,
        ceiling=soprano_midi, floor=max(soprano_midi - 13, bass_midi),
    )
    for alto in alto_cands:
        tenor_cands = _candidate_values(
            chord_pcs, *RANGES["Tenor"], t_tenor,
            ceiling=alto, floor=max(alto - 13, bass_midi),
        )
        for tenor in tenor_cands:
            # Tenor must be above bass with spacing limit
            if tenor <= bass_midi or tenor - bass_midi > 19:
                continue
            voicings.append((alto, tenor))
    if len(voicings) > max_per_beat:
        voicings.sort(key=lambda v: abs(v[0] - t_alto) + abs(v[1] - t_tenor))
        voicings = voicings[:max_per_beat]
    return voicings


def _viterbi_inner_voices(
    melody: list[TypedNote],
    bass_line: list[int],
    beat_data: list[tuple[set[int], list[int]]],
    initial_targets: dict[str, int],
) -> list[dict[str, int]] | None:
    """Find optimal alto+tenor lines via Viterbi with soprano and bass fixed.

    Returns full voicing dicts {Soprano:1, Alto:1, Tenor:1, Bass:1} or None.
    """
    n = len(melody)
    if n == 0:
        return []

    PARALLEL_PENALTY = 1000.0
    INF = float("inf")

    targets = dict(initial_targets)
    candidates: list[list[tuple[int, int]]] = []
    for i in range(n):
        chord_pcs, _ = beat_data[i]
        voicings = _generate_inner_voicings(
            melody[i].midi, bass_line[i], chord_pcs, targets,
        )
        if not voicings:
            return None
        candidates.append(voicings)
        targets = {"Alto:1": voicings[0][0], "Tenor:1": voicings[0][1]}

    # DP
    init_a = initial_targets.get("Alto:1", 64)
    init_t = initial_targets.get("Tenor:1", 55)
    dp_prev = [abs(a - init_a) + abs(t - init_t) for a, t in candidates[0]]
    bp: list[list[int]] = [[-1] * len(candidates[0])]

    for beat in range(1, n):
        curr = candidates[beat]
        prev = candidates[beat - 1]
        s_prev = melody[beat - 1].midi
        s_curr = melody[beat].midi
        b_prev = bass_line[beat - 1]
        b_curr = bass_line[beat]

        dp_curr = [INF] * len(curr)
        bp_curr = [-1] * len(curr)

        for j, (a_c, t_c) in enumerate(curr):
            curr_v = {"Soprano:1": s_curr, "Alto:1": a_c, "Tenor:1": t_c, "Bass:1": b_curr}
            best = INF
            best_k = -1
            for k, (a_p, t_p) in enumerate(prev):
                if dp_prev[k] >= INF:
                    continue
                prev_v = {"Soprano:1": s_prev, "Alto:1": a_p, "Tenor:1": t_p, "Bass:1": b_prev}
                motion = abs(a_c - a_p) + abs(t_c - t_p)
                penalty = PARALLEL_PENALTY if _has_forbidden_parallel(prev_v, curr_v) else 0.0
                total = dp_prev[k] + motion + penalty
                if total < best:
                    best = total
                    best_k = k
            dp_curr[j] = best
            bp_curr[j] = best_k

        dp_prev = dp_curr
        bp.append(bp_curr)

    if all(c >= INF for c in dp_prev):
        return None
    best_final = min(range(len(dp_prev)), key=lambda i: dp_prev[i])
    path = [best_final]
    for beat in range(n - 1, 0, -1):
        path.append(bp[beat][path[-1]])
    path.reverse()

    return [
        {
            "Soprano:1": melody[beat].midi,
            "Alto:1": candidates[beat][path[beat]][0],
            "Tenor:1": candidates[beat][path[beat]][1],
            "Bass:1": bass_line[beat],
        }
        for beat in range(n)
    ]


def _extract_nt_plan(bundle: dict) -> set[tuple[float, str]]:
    """Extract (onset, pitch_class_name) neighbor tone locations from bundle harmony."""
    harmony = bundle.get("deterministic_findings", {}).get("harmony", [])
    plan: set[tuple[float, str]] = set()
    for event in harmony:
        onset = event.get("onset")
        if onset is None:
            continue
        for tag in event.get("nonharmonic_tone_tags", []):
            if tag.startswith("NT:"):
                plan.add((float(onset), tag[3:]))
    return plan


def _insert_neighbor_tones(
    state: CompositionState, nt_plan: set[tuple[float, str]] | None = None, melody_voice: str = "Soprano:1"
) -> None:
    """Insert neighbor tones in inner voices using trial-and-rollback.

    A neighbor tone decorates a held pitch: the note steps up or down by 1-2
    semitones and returns. Applied only at onsets where the bundle indicates NT
    tags (when *nt_plan* is provided), or opportunistically if no plan exists.
    Uses the same trial-and-rollback validation as suspensions: tentatively
    inserts, validates all sub-beat transitions in the region, rolls back if
    any parallel is found.
    """
    if nt_plan is not None and not nt_plan:
        return  # bundle had no NTs

    by_offset: dict[float, dict[str, TypedNote]] = {}
    for note in state.notes:
        by_offset.setdefault(note.offset_quarters, {})[note.voice_id] = note

    offsets = sorted(by_offset.keys())
    all_voices = {"Soprano:1", "Alto:1", "Tenor:1", "Bass:1"}
    # NT plan onsets for gating (if plan provided)
    plan_onsets = {onset for onset, _ in nt_plan} if nt_plan else None

    for i in range(len(offsets) - 1):
        voicing = by_offset[offsets[i]]
        next_voicing = by_offset[offsets[i + 1]]
        if not all_voices <= set(voicing) or not all_voices <= set(next_voicing):
            continue

        # When bundle plan exists, only insert at onsets where NTs were detected
        if plan_onsets is not None and offsets[i] not in plan_onsets:
            continue

        for voice_id in ["Alto:1", "Tenor:1"]:  # inner voices only
            if voice_id == melody_voice:
                continue
            note = voicing.get(voice_id)
            next_note = next_voicing.get(voice_id)
            if note is None or next_note is None or note.midi is None or next_note.midi is None:
                continue
            if note.midi != next_note.midi:
                continue
            if note.duration_quarters < 1.0 or note.fermata:
                continue
            if note.duration_quarters < 0.9:
                continue

            for step in (1, 2, -1, -2):
                nt_midi = note.midi + step
                voice_name = voice_id.split(":")[0]
                low, high = RANGES.get(voice_name, (36, 81))
                if nt_midi < low or nt_midi > high:
                    continue

                shortened = note.duration_quarters - 0.5
                nt_offset = note.offset_quarters + shortened
                nt_note = TypedNote(
                    pitch=midi_to_note_name(nt_midi),
                    midi=nt_midi,
                    duration_quarters=0.5,
                    offset_quarters=nt_offset,
                    measure_number=note.measure_number,
                    beat=note.beat + shortened,
                    voice_id=note.voice_id,
                    part_name=note.part_name,
                )

                # Trial: save original duration, tentatively insert NT
                original_duration = note.duration_quarters
                note.duration_quarters = shortened
                state.add_note(nt_note)

                # Validate: check ALL sub-beat transitions in affected region
                region_start = offsets[i]
                region_end = offsets[i + 1] + (next_note.duration_quarters if next_note else 1.0)
                region_offsets = sorted({
                    n.offset_quarters for n in state._notes
                    if region_start <= n.offset_quarters <= region_end
                })
                parallel_found = False
                for j in range(len(region_offsets) - 1):
                    if _has_forbidden_parallel(
                        state.active_midi_at(region_offsets[j]),
                        state.active_midi_at(region_offsets[j + 1]),
                    ):
                        parallel_found = True
                        break

                # Also check spacing at NT offset
                if not parallel_found:
                    nt_active = state.active_midi_at(nt_offset)
                    for upper, lower, limit in _SPACING_LIMITS:
                        if upper in nt_active and lower in nt_active:
                            if nt_active[upper] - nt_active[lower] > limit:
                                parallel_found = True
                                break

                if parallel_found:
                    # Rollback
                    note.duration_quarters = original_duration
                    state.remove_note(nt_note)
                    continue

                # Commit
                by_offset.setdefault(nt_offset, {})[voice_id] = nt_note
                break  # one NT direction per voice per beat
            else:
                continue
            break  # one NT per beat transition


def _cadence_chord_for_type(cadence_type: str, mode: str = "major") -> tuple[str, str]:
    """Return (penultimate_chord, final_chord) for a cadence type."""
    tonic = "I" if mode == "major" else "i"
    subdom = "IV" if mode == "major" else "iv"
    deceptive = "vi" if mode == "major" else "VI"
    if cadence_type in ("PAC", "IAC"):
        return "V", tonic
    if cadence_type == "HC":
        return subdom, "V"
    if cadence_type == "DC":
        return "V", deceptive
    return "V", tonic


def _insert_passing_tones(state: CompositionState, melody_voice: str = "Soprano:1") -> None:
    """Insert passing tones in inner voices using CompositionState for parallel checking."""
    by_offset: dict[float, dict[str, TypedNote]] = {}
    for note in state.notes:
        by_offset.setdefault(note.offset_quarters, {})[note.voice_id] = note

    offsets = sorted(by_offset.keys())

    for i in range(len(offsets) - 1):
        voicing = by_offset[offsets[i]]
        next_voicing = by_offset[offsets[i + 1]]

        # Skip beats where a suspension already modified notes
        if any(n.duration_quarters < 0.9 for n in voicing.values() if n.voice_id != melody_voice):
            continue

        for voice_id in ["Alto:1", "Tenor:1", "Bass:1"]:
            note = voicing.get(voice_id)
            next_note = next_voicing.get(voice_id)
            if note is None or next_note is None or note.midi is None or next_note.midi is None:
                continue
            interval = abs(next_note.midi - note.midi)
            if interval not in {3, 4} or note.duration_quarters < 1.0 or note.fermata:
                continue

            pt_midi = round((note.midi + next_note.midi) / 2)
            shortened = note.duration_quarters - 0.5

            # Use CompositionState for parallel checking — sees all active notes
            current_active = state.active_midi_at(offsets[i])
            pt_active = dict(current_active)
            pt_active[voice_id] = pt_midi
            next_active = state.active_midi_at(offsets[i + 1])

            if _has_forbidden_parallel(current_active, pt_active):
                continue
            if _has_forbidden_parallel(pt_active, next_active):
                continue

            spacing_ok = True
            for upper, lower, limit in _SPACING_LIMITS:
                if upper in pt_active and lower in pt_active:
                    if pt_active[upper] - pt_active[lower] > limit:
                        spacing_ok = False
                        break
            if not spacing_ok:
                continue

            # Apply — mutate duration (state sees via reference), add PT to state
            note.duration_quarters = shortened
            pt_offset = note.offset_quarters + shortened
            pt_note = TypedNote(
                pitch=midi_to_note_name(pt_midi),
                midi=pt_midi,
                duration_quarters=0.5,
                offset_quarters=pt_offset,
                measure_number=note.measure_number,
                beat=note.beat + shortened,
                voice_id=note.voice_id,
                part_name=note.part_name,
            )
            state.add_note(pt_note)
            by_offset.setdefault(pt_offset, {})[voice_id] = pt_note
            break  # one PT per beat transition


def _insert_suspensions(
    state: CompositionState, suspension_plan: set[tuple[int, str]], melody_voice: str = "Soprano:1"
) -> None:
    """Insert suspensions using trial-and-rollback with CompositionState validation.

    For each candidate suspension, tentatively inserts it into the state, then
    checks ALL sub-beat transitions in the affected region. If any parallel is
    found, the insertion is rolled back. This guarantees suspensions never
    introduce parallel violations regardless of PT interactions.
    """
    if not suspension_plan:
        return

    by_offset: dict[float, dict[str, TypedNote]] = {}
    for note in state.notes:
        by_offset.setdefault(note.offset_quarters, {})[note.voice_id] = note

    offsets = sorted(by_offset.keys())
    inner_voices = [voice_id for voice_id in ["Alto:1", "Tenor:1", "Bass:1"] if voice_id != melody_voice]
    all_voices = {"Soprano:1", "Alto:1", "Tenor:1", "Bass:1"}

    for i in range(len(offsets) - 1):
        voicing = by_offset[offsets[i]]
        next_voicing = by_offset[offsets[i + 1]]
        if not all_voices <= set(voicing) or not all_voices <= set(next_voicing):
            continue

        for voice_id in inner_voices:
            note = voicing.get(voice_id)
            next_note = next_voicing.get(voice_id)
            if note is None or next_note is None or note.midi is None or next_note.midi is None:
                continue
            if (next_note.measure_number, voice_id) not in suspension_plan:
                continue
            if note.midi - next_note.midi not in {1, 2}:
                continue
            if next_note.duration_quarters < 1.0:
                continue

            # Quick pre-check with current state before tentative insert
            current_active = state.active_midi_at(offsets[i])
            next_active = state.active_midi_at(offsets[i + 1])
            suspension_active = dict(next_active)
            suspension_active[voice_id] = note.midi

            if _has_forbidden_parallel(current_active, suspension_active):
                continue

            spacing_ok = True
            for upper, lower, limit in _SPACING_LIMITS:
                if upper in suspension_active and lower in suspension_active:
                    if suspension_active[upper] - suspension_active[lower] > limit:
                        spacing_ok = False
                        break
            if not spacing_ok:
                continue

            # Build suspension and resolution notes
            suspension_note = TypedNote(
                pitch=midi_to_note_name(note.midi),
                midi=note.midi,
                duration_quarters=0.5,
                offset_quarters=next_note.offset_quarters,
                measure_number=next_note.measure_number,
                beat=next_note.beat,
                voice_id=next_note.voice_id,
                staff_id=next_note.staff_id,
                part_name=next_note.part_name,
                source_ref=next_note.source_ref,
            )
            resolution_offset = next_note.offset_quarters + 0.5
            resolution_note = TypedNote(
                pitch=midi_to_note_name(next_note.midi),
                midi=next_note.midi,
                duration_quarters=next_note.duration_quarters - 0.5,
                offset_quarters=resolution_offset,
                measure_number=next_note.measure_number,
                beat=next_note.beat + 0.5,
                voice_id=next_note.voice_id,
                staff_id=next_note.staff_id,
                part_name=next_note.part_name,
                fermata=next_note.fermata,
                source_ref=next_note.source_ref,
            )

            # Tentatively insert into state
            state.remove_note(next_note)
            state.add_note(suspension_note)
            state.add_note(resolution_note)

            # Validate: check ALL sub-beat transitions in the affected region
            region_start = offsets[i]
            region_end = resolution_offset + next_note.duration_quarters
            region_offsets = sorted({
                n.offset_quarters for n in state._notes
                if region_start <= n.offset_quarters <= region_end
            })
            parallel_found = False
            for j in range(len(region_offsets) - 1):
                if _has_forbidden_parallel(
                    state.active_midi_at(region_offsets[j]),
                    state.active_midi_at(region_offsets[j + 1]),
                ):
                    parallel_found = True
                    break

            if parallel_found:
                # Rollback
                state.remove_note(suspension_note)
                state.remove_note(resolution_note)
                state.add_note(next_note)
                continue

            # Commit — update by_offset for subsequent iterations
            next_voicing[voice_id] = suspension_note
            by_offset.setdefault(resolution_offset, {})[voice_id] = resolution_note
            break


def harmonize_chorale_melody(melody_graph: EventGraph, artifact_id: str = "ART-00001", bundle: dict | None = None) -> tuple[EventGraph, list[str]]:
    voice_id = melody_graph.ordered_voice_ids()[0]
    melody = [note for note in melody_graph.notes_by_voice()[voice_id] if note.midi is not None and not note.is_rest]
    key = melody_graph.metadata.key_estimate
    global_tonic = key.tonic if key else "C"
    mode = key.mode if key else "major"
    defaults = DEFAULT_DEGREE_CHORD_MINOR if mode == "minor" else DEFAULT_DEGREE_CHORD_MAJOR
    degree_chord_map = _extract_degree_chord_map(bundle, global_tonic, mode) if bundle else defaults.copy()
    onset_chord_plan = _extract_onset_chord_plan(bundle) if bundle else []
    cadence_plan = _extract_cadence_plan(bundle) if bundle else []
    cadence_measures = {c["measure"]: c["cadence_type"] for c in cadence_plan}
    local_key_map = _extract_local_key_map(bundle) if bundle else {}
    previous_targets = {"Alto:1": 64, "Tenor:1": 55, "Bass:1": 43}
    previous_mapping: dict[str, int] = {}
    trace = [f"Estimated key: {global_tonic} {mode}"]
    if bundle:
        trace.append(f"Using evidence bundle: {len(cadence_plan)} cadence(s), {len(onset_chord_plan)} harmonic event(s), {len(set(local_key_map.values()))} local key(s)")
    # Pre-build measure → note-index list for cadence targeting
    measure_note_indices: dict[int, list[int]] = {}
    for idx, n in enumerate(melody):
        measure_note_indices.setdefault(n.measure_number, []).append(idx)

    # ── Pre-compute per-beat chord data ──
    beat_chord_labels: list[str] = []
    beat_data: list[tuple[set[int], list[int]]] = []  # (chord_pcs, bass_pc_options)
    for index, note in enumerate(melody):
        tonic = local_key_map.get(note.measure_number, global_tonic)
        onset_chord = _lookup_chord_at_onset(onset_chord_plan, note.offset_quarters)
        if onset_chord:
            chord_label = onset_chord
        else:
            degree = _degree(note.midi, tonic)
            chord_label = degree_chord_map.get(degree, "I" if mode == "major" else "i")
        is_final = index == len(melody) - 1
        is_penultimate = index == len(melody) - 2
        if note.measure_number in cadence_measures:
            indices_in_measure = measure_note_indices[note.measure_number]
            pos = indices_in_measure.index(index)
            is_last = pos == len(indices_in_measure) - 1
            is_penult_in_measure = pos == len(indices_in_measure) - 2
            cad_type = cadence_measures[note.measure_number]
            if is_last:
                _, final_chord = _cadence_chord_for_type(cad_type, mode)
                chord_label = final_chord
                trace.append(f"  [cadence: {cad_type} → {chord_label} at m{note.measure_number}]")
            elif is_penult_in_measure:
                penult_chord, _ = _cadence_chord_for_type(cad_type, mode)
                chord_label = penult_chord
                trace.append(f"  [cadence approach: {penult_chord} at m{note.measure_number}]")
        elif is_final:
            chord_label = "I" if mode == "major" else "i"
        elif is_penultimate:
            chord_label = "V"
        tonic_pc = NOTE_TO_PC[tonic]
        if chord_label in ALL_CHORDS:
            chord_pcs = {(tonic_pc + interval) % 12 for interval in ALL_CHORDS[chord_label]}
        else:
            sec_dom = _resolve_secondary_dominant(chord_label)
            if sec_dom is not None:
                chord_pcs = {(tonic_pc + interval) % 12 for interval in sec_dom}
            else:
                chord_pcs = {(tonic_pc + interval) % 12 for interval in ALL_CHORDS.get("I", {0, 4, 7})}
        chord_ints = CHORD_INTERVALS.get(chord_label) or _resolve_secondary_dominant(chord_label) or (0,)
        if is_penultimate and chord_label in ("V", "V7"):
            bass_pc_options = [(tonic_pc + 2) % 12]
        else:
            bass_pc_options = list(dict.fromkeys((tonic_pc + interval) % 12 for interval in chord_ints[:3]))
        beat_chord_labels.append(chord_label)
        beat_data.append((chord_pcs, bass_pc_options))

    # ── Baseline secondary dominant heuristic (when no evidence bundle) ──
    _SEC_DOM_BEFORE = {
        "V": "V/V", "V7": "V/V", "vi": "V/vi", "VI": "V/VI",
        "ii": "V/ii", "ii7": "V/ii", "ii°": "V/ii",
    }
    _SEC_DOM_SKIP = frozenset({"V", "V7", "vii°", "viiø7", "viio7"})
    if not onset_chord_plan:
        for i in range(len(beat_chord_labels) - 1):
            next_chord = beat_chord_labels[i + 1]
            curr_chord = beat_chord_labels[i]
            sec_label = _SEC_DOM_BEFORE.get(next_chord)
            if sec_label and "/" not in curr_chord and curr_chord not in _SEC_DOM_SKIP:
                tonic = local_key_map.get(melody[i].measure_number, global_tonic)
                tonic_pc = NOTE_TO_PC[tonic]
                sec_ints = CHORD_INTERVALS.get(sec_label) or _resolve_secondary_dominant(sec_label)
                if sec_ints is not None:
                    new_pcs = {(tonic_pc + interval) % 12 for interval in sec_ints}
                    bass_opts = list(dict.fromkeys((tonic_pc + interval) % 12 for interval in sec_ints[:3]))
                    beat_chord_labels[i] = sec_label
                    beat_data[i] = (new_pcs, bass_opts)
                    trace.append(f"  [baseline sec.dom: {sec_label} at m{melody[i].measure_number}]")

    # ── Primary: Two-phase outer-then-inner composition ──
    per_beat_tonic_pcs = [
        NOTE_TO_PC[local_key_map.get(note.measure_number, global_tonic)]
        for note in melody
    ]
    bass_line = _viterbi_bass_line(
        melody, beat_data, beat_chord_labels,
        initial_bass=previous_targets.get("Bass:1", 43),
        tonic_pcs=per_beat_tonic_pcs,
    )
    voicing_sequence: list[dict[str, int]] | None = None
    if bass_line is not None:
        voicing_sequence = _viterbi_inner_voices(
            melody, bass_line, beat_data,
            {"Alto:1": previous_targets["Alto:1"], "Tenor:1": previous_targets["Tenor:1"]},
        )
        if voicing_sequence is not None:
            trace.append("[solver: two-phase outer+inner]")

    # Fallback: original joint Viterbi
    if voicing_sequence is None:
        voicing_sequence = _viterbi_voicings(melody, beat_data, previous_targets)

    notes: list[TypedNote] = []
    if voicing_sequence is not None:
        trace.append("[solver: viterbi]")
        for index, (note, chosen) in enumerate(zip(melody, voicing_sequence)):
            trace.append(f"m{note.measure_number} beat {note.beat}: {beat_chord_labels[index]}")
            for gen_voice, midi in chosen.items():
                notes.append(
                    TypedNote(
                        pitch=midi_to_note_name(midi),
                        midi=midi,
                        duration_quarters=note.duration_quarters,
                        offset_quarters=note.offset_quarters,
                        measure_number=note.measure_number,
                        beat=note.beat,
                        voice_id=gen_voice,
                        part_name=gen_voice.split(":", 1)[0],
                        fermata=note.fermata,
                    )
                )
    else:
        # ── Fallback: greedy search (original algorithm) ──
        trace.append("[solver: greedy-fallback]")
        previous_mapping: dict[str, int] = {}
        for index, note in enumerate(melody):
            chord_pcs, bass_pc_options = beat_data[index]
            chord_label = beat_chord_labels[index]
            alto_candidates = _candidate_values(chord_pcs, *RANGES["Alto"], previous_targets["Alto:1"], ceiling=note.midi, floor=note.midi - 13)
            chosen: dict[str, int] | None = None
            first_valid: dict[str, int] | None = None
            for bass_pc in bass_pc_options:
                for alto in alto_candidates or [previous_targets["Alto:1"]]:
                    tenor_candidates = _candidate_values(chord_pcs, *RANGES["Tenor"], previous_targets["Tenor:1"], ceiling=alto, floor=alto - 13)
                    for tenor in tenor_candidates or [previous_targets["Tenor:1"]]:
                        bass_candidates = _candidate_values({bass_pc}, *RANGES["Bass"], previous_targets["Bass:1"], ceiling=tenor, floor=tenor - 20)
                        for bass in bass_candidates or [previous_targets["Bass:1"]]:
                            current = {"Soprano:1": note.midi, "Alto:1": alto, "Tenor:1": tenor, "Bass:1": bass}
                            if first_valid is None:
                                first_valid = current
                            if not _has_forbidden_parallel(previous_mapping, current):
                                chosen = current
                                break
                        if chosen:
                            break
                    if chosen:
                        break
                if chosen:
                    break
            if chosen is None and first_valid is not None:
                chosen = first_valid
            if chosen is None:
                fb_alto = _fallback(alto_candidates, previous_targets["Alto:1"])
                fb_tenor = _fallback(
                    _candidate_values(chord_pcs, *RANGES["Tenor"], previous_targets["Tenor:1"], ceiling=fb_alto, floor=fb_alto - 13),
                    previous_targets["Tenor:1"],
                )
                fb_bass_pc = bass_pc_options[0]
                chosen = {
                    "Soprano:1": note.midi,
                    "Alto:1": fb_alto,
                    "Tenor:1": fb_tenor,
                    "Bass:1": _fallback(
                        _candidate_values({fb_bass_pc}, *RANGES["Bass"], previous_targets["Bass:1"], ceiling=fb_tenor, floor=fb_tenor - 20),
                        previous_targets["Bass:1"],
                    ),
                }
            trace.append(f"m{note.measure_number} beat {note.beat}: {chord_label}")
            for gen_voice, midi in chosen.items():
                notes.append(
                    TypedNote(
                        pitch=midi_to_note_name(midi),
                        midi=midi,
                        duration_quarters=note.duration_quarters,
                        offset_quarters=note.offset_quarters,
                        measure_number=note.measure_number,
                        beat=note.beat,
                        voice_id=gen_voice,
                        part_name=gen_voice.split(":", 1)[0],
                        fermata=note.fermata,
                    )
                )
            previous_targets = {voice: midi for voice, midi in chosen.items() if voice != "Soprano:1"}
            previous_mapping = chosen
    if bundle is not None:
        state = CompositionState(notes)
        _insert_passing_tones(state)
        suspension_plan = _extract_suspension_plan(bundle)
        _insert_suspensions(state, suspension_plan)
        nt_plan = _extract_nt_plan(bundle)
        _insert_neighbor_tones(state, nt_plan)
        notes = sorted(state.notes, key=lambda n: (n.offset_quarters, n.voice_id, n.midi or -1))
    section = Section(section_id=f"{artifact_id}:section:1", work_id=artifact_id, label="Generated chorale study", section_type="chorale-study", measure_start=1, measure_end=max(note.measure_number for note in melody))
    metadata = EncodingMetadata(encoding_id=artifact_id, work_id=artifact_id, title="Bachbot chorale study", composer="Bachbot", source_format="internal", key_estimate=key, provenance=["Generated from melody under deterministic SATB constraints"])
    voices = [Voice(voice_id="Soprano:1", section_id=section.section_id, part_name="Soprano", normalized_voice_name="Soprano"), Voice(voice_id="Alto:1", section_id=section.section_id, part_name="Alto", normalized_voice_name="Alto"), Voice(voice_id="Tenor:1", section_id=section.section_id, part_name="Tenor", normalized_voice_name="Tenor"), Voice(voice_id="Bass:1", section_id=section.section_id, part_name="Bass", normalized_voice_name="Bass")]
    return EventGraph(metadata=metadata, section=section, voices=voices, notes=notes), trace
