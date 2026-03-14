"""Two-part invention generator.

Generates a two-voice polyphonic invention in the style of J.S. Bach's
Two-Part Inventions (BWV 772–786).  The generator builds the standard
form: subject → tonal answer with countersubject → sequential episode →
subject in the complementary voice.

All output is deterministic given a fixed seed.
"""

from __future__ import annotations

import random
from typing import Literal

from pydantic import Field

from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.encodings.musicxml_io import midi_to_note_name, note_name_to_midi
from bachbot.models.base import BachbotModel, KeyEstimate, TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice

# ---------------------------------------------------------------------------
# Pitch / scale helpers
# ---------------------------------------------------------------------------

NOTE_TO_PC: dict[str, int] = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}

_MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
_MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)

PERFECT_INTERVALS = {0, 7}  # unison and fifth (mod 12)
CONSONANT_INTERVALS = {0, 3, 4, 7, 8, 9}  # P1, m3, M3, P5, m6, M6


def _scale_pcs(tonic_pc: int, mode: str) -> list[int]:
    """Return the 7 pitch-classes of the diatonic scale."""
    base = _MAJOR_SCALE if mode == "major" else _MINOR_SCALE
    return [(tonic_pc + s) % 12 for s in base]


def _scale_degrees(tonic_pc: int, mode: str) -> dict[int, int]:
    """Map pitch-class → 0-based scale degree (0..6)."""
    pcs = _scale_pcs(tonic_pc, mode)
    return {pc: i for i, pc in enumerate(pcs)}


def _nearest_scale_midi(midi: int, tonic_pc: int, mode: str) -> int:
    """Snap a MIDI pitch to the nearest diatonic scale tone."""
    pcs = set(_scale_pcs(tonic_pc, mode))
    if midi % 12 in pcs:
        return midi
    for offset in (1, -1, 2, -2):
        if (midi + offset) % 12 in pcs:
            return midi + offset
    return midi  # fallback


def _dominant_tonic_pc(tonic_pc: int) -> int:
    """Return the dominant pitch-class (a fifth above the tonic)."""
    return (tonic_pc + 7) % 12


def pitch_name_to_midi(name: str) -> int:
    """Convert 'C4', 'F#3', etc. to MIDI number."""
    return note_name_to_midi(name)


def midi_to_pitch_name(midi: int) -> str:
    """Convert MIDI number to pitch name like 'C4'."""
    return midi_to_note_name(midi)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class InventionConfig(BachbotModel):
    key_tonic: str = "C"
    mode: str = "major"
    meter: str = "4/4"
    upper_range: tuple[int, int] = (60, 79)   # right hand
    lower_range: tuple[int, int] = (40, 64)   # left hand
    seed: int = 42


class SubjectEntry(BachbotModel):
    voice: str  # "upper" or "lower"
    start_onset: float
    notes: list[TypedNote]


# ---------------------------------------------------------------------------
# Tonal answer
# ---------------------------------------------------------------------------


def generate_tonal_answer(
    subject_notes: list[TypedNote],
    *,
    key_tonic: str = "C",
    mode: str = "major",
) -> list[TypedNote]:
    """Transpose the subject to the dominant with tonal mutation.

    Tonal answer rules:
    - Scale degree 1 in the tonic maps to degree 5 in the answer (not a
      literal transposition up a 5th which would give degree 2 of dominant).
    - Scale degree 5 in the tonic maps to degree 1 of the dominant.
    - All other degrees are transposed diatonically to the dominant key.
    """
    tonic_pc = NOTE_TO_PC[key_tonic]
    dom_pc = _dominant_tonic_pc(tonic_pc)

    tonic_degrees = _scale_degrees(tonic_pc, mode)
    dom_scale = _scale_pcs(dom_pc, mode)

    answer_notes: list[TypedNote] = []
    for note in subject_notes:
        if note.is_rest or note.midi is None:
            answer_notes.append(note.model_copy())
            continue

        pc = note.midi % 12
        octave = note.midi // 12

        # Find scale degree in the tonic key
        deg = tonic_degrees.get(pc)

        if deg is not None:
            # Tonal mutation: degree 0 (tonic) → degree 4 (dom of dom key = 5th of tonic)
            # degree 4 (dominant of tonic) → degree 0 (tonic of dom key)
            if deg == 0:
                target_deg = 4  # 5th degree in dominant key
            elif deg == 4:
                target_deg = 0  # 1st degree in dominant key
            else:
                # Standard diatonic transposition: shift degree by the
                # relationship between tonic and dominant.
                # Dominant is degree 4 in the tonic scale, so we shift
                # each degree up by 4 (mod 7) in scale-degree space.
                target_deg = (deg + 4) % 7

            target_pc = dom_scale[target_deg]
        else:
            # Chromatic note — literal transposition up a 5th
            target_pc = (pc + 7) % 12

        # Find closest octave placement to original
        target_midi = octave * 12 + target_pc
        # Adjust octave to stay close to original pitch
        while target_midi < note.midi - 6:
            target_midi += 12
        while target_midi > note.midi + 8:
            target_midi -= 12

        answer_notes.append(
            TypedNote(
                pitch=midi_to_note_name(target_midi),
                midi=target_midi,
                duration_quarters=note.duration_quarters,
                offset_quarters=note.offset_quarters,
                measure_number=note.measure_number,
                beat=note.beat,
                voice_id=note.voice_id,
            )
        )

    return answer_notes


# ---------------------------------------------------------------------------
# Countersubject
# ---------------------------------------------------------------------------


def _interval_class(midi_a: int, midi_b: int) -> int:
    """Return the interval mod 12 between two pitches."""
    return abs(midi_a - midi_b) % 12


def _is_consonant(midi_a: int, midi_b: int) -> bool:
    return _interval_class(midi_a, midi_b) in CONSONANT_INTERVALS


def _motion_dir(prev: int, curr: int) -> int:
    if curr > prev:
        return 1
    if curr < prev:
        return -1
    return 0


def _has_parallel_perfect(prev_a: int, curr_a: int, prev_b: int, curr_b: int) -> bool:
    """Check if moving from (prev_a, prev_b) to (curr_a, curr_b) creates parallel 5ths/8ves."""
    prev_iv = abs(prev_a - prev_b) % 12
    curr_iv = abs(curr_a - curr_b) % 12
    if prev_iv in PERFECT_INTERVALS and curr_iv in PERFECT_INTERVALS:
        ma = _motion_dir(prev_a, curr_a)
        mb = _motion_dir(prev_b, curr_b)
        if ma == mb != 0 and prev_iv == curr_iv:
            return True
    return False


def generate_countersubject(
    subject_notes: list[TypedNote],
    answer_notes: list[TypedNote],
    *,
    key_tonic: str = "C",
    mode: str = "major",
    rng: random.Random | None = None,
) -> list[TypedNote]:
    """Generate a countersubject that sounds against *answer_notes*.

    The countersubject prefers contrary motion and consonant intervals
    (3rds, 6ths, 10ths) on strong beats.  It is built one note at a time
    using constrained search.
    """
    if rng is None:
        rng = random.Random(42)

    tonic_pc = NOTE_TO_PC[key_tonic]
    scale_set = set(_scale_pcs(tonic_pc, mode))

    cs_notes: list[TypedNote] = []
    prev_cs_midi: int | None = None

    for i, ans_note in enumerate(answer_notes):
        if ans_note.is_rest or ans_note.midi is None:
            cs_notes.append(
                TypedNote(
                    pitch=None, midi=None, is_rest=True,
                    duration_quarters=ans_note.duration_quarters,
                    offset_quarters=ans_note.offset_quarters,
                    measure_number=ans_note.measure_number,
                    beat=ans_note.beat,
                    voice_id="Upper:1",
                )
            )
            continue

        ans_midi = ans_note.midi
        beat = ans_note.beat

        # Determine whether this is a strong beat (1 or 3 in 4/4)
        is_strong = beat in (1.0, 3.0)

        # Generate candidates: diatonic pitches within a reasonable range
        # Countersubject is typically above the answer (in the upper voice)
        low = ans_midi + 2
        high = ans_midi + 19

        candidates: list[int] = []
        for m in range(low, high + 1):
            if m % 12 not in scale_set:
                continue
            iv = _interval_class(m, ans_midi)
            if is_strong:
                # Strong beat: must be consonant
                if iv not in CONSONANT_INTERVALS:
                    continue
            # Weak beat: allow passing dissonance (2nds, 7ths)
            candidates.append(m)

        if not candidates:
            # Fallback: any diatonic pitch in range
            candidates = [m for m in range(low, high + 1) if m % 12 in scale_set]
        if not candidates:
            candidates = [ans_midi + 7]  # last resort: a fifth above

        # Score candidates
        def _score(m: int) -> float:
            s = 0.0
            iv = _interval_class(m, ans_midi)
            # Prefer consonances
            if iv in CONSONANT_INTERVALS:
                s -= 5.0
            # Prefer 3rds and 6ths over perfect intervals
            if iv in {3, 4, 8, 9}:
                s -= 3.0
            # Prefer stepwise motion
            if prev_cs_midi is not None:
                step = abs(m - prev_cs_midi)
                if step <= 2:
                    s -= 4.0
                elif step <= 4:
                    s -= 1.0
                else:
                    s += step * 0.5
                # Prefer contrary motion to answer
                if i > 0 and answer_notes[i - 1].midi is not None:
                    ans_dir = _motion_dir(answer_notes[i - 1].midi, ans_midi)
                    cs_dir = _motion_dir(prev_cs_midi, m)
                    if cs_dir != 0 and cs_dir != ans_dir:
                        s -= 3.0  # contrary motion bonus
                # Avoid parallel perfects
                if i > 0 and answer_notes[i - 1].midi is not None:
                    if _has_parallel_perfect(prev_cs_midi, m, answer_notes[i - 1].midi, ans_midi):
                        s += 50.0
            return s

        candidates.sort(key=lambda m: (_score(m), rng.random()))
        chosen = candidates[0]

        cs_notes.append(
            TypedNote(
                pitch=midi_to_note_name(chosen),
                midi=chosen,
                duration_quarters=ans_note.duration_quarters,
                offset_quarters=ans_note.offset_quarters,
                measure_number=ans_note.measure_number,
                beat=ans_note.beat,
                voice_id="Upper:1",
            )
        )
        prev_cs_midi = chosen

    return cs_notes


# ---------------------------------------------------------------------------
# Episode generation
# ---------------------------------------------------------------------------


def generate_episode(
    subject_notes: list[TypedNote],
    *,
    key_tonic: str = "C",
    mode: str = "major",
    target_key: str = "G",
    measures: int = 2,
    rng: random.Random | None = None,
) -> tuple[list[TypedNote], list[TypedNote]]:
    """Build a sequential episode from a subject motif.

    Extracts the first 4-6 notes of the subject as a motif, then sequences
    it at descending scale-step intervals.  The second voice follows in
    imitation offset by 1 beat.

    Returns (upper_notes, lower_notes).
    """
    if rng is None:
        rng = random.Random(42)

    tonic_pc = NOTE_TO_PC[key_tonic]
    target_pc = NOTE_TO_PC[target_key]
    scale = _scale_pcs(tonic_pc, mode)
    target_scale = _scale_pcs(target_pc, mode)

    # Extract motif: first 4-6 notes (prefer 4)
    motif_len = min(max(4, len(subject_notes) // 2), 6, len(subject_notes))
    motif = subject_notes[:motif_len]

    # Calculate motif duration
    motif_dur = sum(n.duration_quarters for n in motif)

    # Number of sequence repetitions
    beats_per_measure = 4.0  # assume 4/4
    total_beats = measures * beats_per_measure
    n_reps = max(2, int(total_beats / motif_dur)) if motif_dur > 0 else 2

    # Determine step size for descending sequence (in semitones)
    # We'll descend by scale steps (roughly 2 semitones)
    deg_map = _scale_degrees(tonic_pc, mode)

    upper_notes: list[TypedNote] = []
    lower_notes: list[TypedNote] = []

    # Start measure/onset for the episode
    # These will be set by the caller via offset adjustment; here we use
    # relative positions starting from 0
    onset_base = 0.0
    measure_base = 1

    for rep in range(n_reps):
        # Transposition: descend by (rep * scale_step) semitones
        transpose_semis = -2 * rep  # descend by seconds

        # Gradually shift toward target key
        if n_reps > 1:
            blend = rep / (n_reps - 1)
        else:
            blend = 0.0

        for j, note in enumerate(motif):
            if note.is_rest or note.midi is None:
                continue

            upper_midi = note.midi + transpose_semis
            # Snap to diatonic if needed
            if blend < 0.5:
                upper_midi = _nearest_scale_midi(upper_midi, tonic_pc, mode)
            else:
                upper_midi = _nearest_scale_midi(upper_midi, target_pc, mode)

            note_onset = onset_base + sum(m.duration_quarters for m in motif[:j])
            note_measure = measure_base + int(note_onset // beats_per_measure)
            note_beat = 1.0 + (note_onset % beats_per_measure)

            upper_notes.append(
                TypedNote(
                    pitch=midi_to_note_name(upper_midi),
                    midi=upper_midi,
                    duration_quarters=note.duration_quarters,
                    offset_quarters=note_onset,
                    measure_number=note_measure,
                    beat=note_beat,
                    voice_id="Upper:1",
                )
            )

            # Lower voice: imitation offset by 1 beat, a 6th or 10th below
            lower_midi = upper_midi - 9  # minor 6th below (≈ 10th inverted)
            if blend < 0.5:
                lower_midi = _nearest_scale_midi(lower_midi, tonic_pc, mode)
            else:
                lower_midi = _nearest_scale_midi(lower_midi, target_pc, mode)

            lower_onset = note_onset + 1.0  # 1 beat offset
            lower_measure = measure_base + int(lower_onset // beats_per_measure)
            lower_beat = 1.0 + (lower_onset % beats_per_measure)

            lower_notes.append(
                TypedNote(
                    pitch=midi_to_note_name(lower_midi),
                    midi=lower_midi,
                    duration_quarters=note.duration_quarters,
                    offset_quarters=lower_onset,
                    measure_number=lower_measure,
                    beat=lower_beat,
                    voice_id="Lower:1",
                )
            )

        onset_base += motif_dur

    return upper_notes, lower_notes


# ---------------------------------------------------------------------------
# Helper: shift notes to a new starting position
# ---------------------------------------------------------------------------


def _shift_notes(
    notes: list[TypedNote],
    *,
    onset_offset: float,
    measure_offset: int,
    voice_id: str,
    transpose: int = 0,
    beats_per_measure: float = 4.0,
) -> list[TypedNote]:
    """Return copies of *notes* shifted in time and optionally transposed."""
    if not notes:
        return []
    # Base onset of the original notes
    base_onset = notes[0].offset_quarters
    shifted: list[TypedNote] = []
    for note in notes:
        relative = note.offset_quarters - base_onset
        new_onset = onset_offset + relative
        new_measure = measure_offset + int(new_onset // beats_per_measure)
        new_beat = 1.0 + (new_onset % beats_per_measure)
        midi = (note.midi + transpose) if note.midi is not None else None
        pitch = midi_to_note_name(midi) if midi is not None else None
        shifted.append(
            TypedNote(
                pitch=pitch,
                midi=midi,
                duration_quarters=note.duration_quarters,
                offset_quarters=new_onset,
                measure_number=new_measure,
                beat=new_beat,
                voice_id=voice_id,
                is_rest=note.is_rest,
            )
        )
    return shifted


def _clamp_to_range(notes: list[TypedNote], lo: int, hi: int) -> list[TypedNote]:
    """Octave-shift notes that fall outside [lo, hi]."""
    result: list[TypedNote] = []
    for n in notes:
        if n.midi is None or n.is_rest:
            result.append(n)
            continue
        m = n.midi
        while m < lo:
            m += 12
        while m > hi:
            m -= 12
        if m == n.midi:
            result.append(n)
        else:
            result.append(
                n.model_copy(update={"midi": m, "pitch": midi_to_note_name(m)})
            )
    return result


# ---------------------------------------------------------------------------
# Main: generate_invention
# ---------------------------------------------------------------------------


def generate_invention(
    subject_notes: list[TypedNote],
    *,
    config: InventionConfig | None = None,
) -> EventGraph:
    """Generate a two-part invention from a subject.

    Structure (standard invention form):
      mm. 1–2  Subject in upper voice alone
      mm. 3–4  Answer in lower voice + countersubject in upper voice
      mm. 5–6  Episode 1 (sequential, modulating to dominant)
      mm. 7–8  Subject in lower voice (dominant key) + countersubject in upper

    Returns an ``EventGraph`` with two voices: Upper:1 and Lower:1.
    """
    if config is None:
        config = InventionConfig()

    rng = random.Random(config.seed)
    beats_per_measure = 4.0  # 4/4 time

    tonic_pc = NOTE_TO_PC[config.key_tonic]
    dom_pc = _dominant_tonic_pc(tonic_pc)
    # Find dominant key name
    _pc_to_name = {v: k for k, v in NOTE_TO_PC.items() if len(k) <= 2}
    # Prefer sharp spelling for dominants
    _pc_to_name_map = {
        0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F",
        6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B",
    }
    dom_key = _pc_to_name_map[dom_pc]

    all_upper: list[TypedNote] = []
    all_lower: list[TypedNote] = []

    # --- Section 1: mm. 1-2 — Subject in upper voice ---
    subject_dur = sum(n.duration_quarters for n in subject_notes)
    # If subject is shorter than 2 measures, pad; if longer, it spans more measures
    section1_measures = max(2, int((subject_dur + beats_per_measure - 0.01) // beats_per_measure))

    upper_subj = _shift_notes(
        subject_notes, onset_offset=0.0, measure_offset=1,
        voice_id="Upper:1", beats_per_measure=beats_per_measure,
    )
    upper_subj = _clamp_to_range(upper_subj, config.upper_range[0], config.upper_range[1])
    all_upper.extend(upper_subj)

    # Lower voice is silent during section 1 (no notes needed)

    # --- Section 2: mm. 3-4 — Answer in lower voice + countersubject in upper ---
    section2_onset = section1_measures * beats_per_measure
    section2_measure = 1 + section1_measures

    # Generate tonal answer
    answer = generate_tonal_answer(subject_notes, key_tonic=config.key_tonic, mode=config.mode)

    # Shift answer to lower voice at section 2 onset, transposed down an octave
    lower_answer = _shift_notes(
        answer, onset_offset=section2_onset, measure_offset=section2_measure,
        voice_id="Lower:1", transpose=-12, beats_per_measure=beats_per_measure,
    )
    lower_answer = _clamp_to_range(lower_answer, config.lower_range[0], config.lower_range[1])
    all_lower.extend(lower_answer)

    # Generate countersubject against the answer (in the original octave range)
    cs = generate_countersubject(
        subject_notes, answer, key_tonic=config.key_tonic, mode=config.mode, rng=rng,
    )
    upper_cs = _shift_notes(
        cs, onset_offset=section2_onset, measure_offset=section2_measure,
        voice_id="Upper:1", beats_per_measure=beats_per_measure,
    )
    upper_cs = _clamp_to_range(upper_cs, config.upper_range[0], config.upper_range[1])
    all_upper.extend(upper_cs)

    answer_dur = sum(n.duration_quarters for n in answer)
    section2_measures = max(2, int((answer_dur + beats_per_measure - 0.01) // beats_per_measure))

    # --- Section 3: mm. 5-6 — Episode ---
    section3_onset = section2_onset + section2_measures * beats_per_measure
    section3_measure = section2_measure + section2_measures

    ep_upper, ep_lower = generate_episode(
        subject_notes,
        key_tonic=config.key_tonic,
        mode=config.mode,
        target_key=dom_key,
        measures=2,
        rng=rng,
    )

    ep_upper_shifted = _shift_notes(
        ep_upper, onset_offset=section3_onset, measure_offset=section3_measure,
        voice_id="Upper:1", beats_per_measure=beats_per_measure,
    )
    ep_lower_shifted = _shift_notes(
        ep_lower, onset_offset=section3_onset, measure_offset=section3_measure,
        voice_id="Lower:1", beats_per_measure=beats_per_measure,
    )
    ep_upper_shifted = _clamp_to_range(ep_upper_shifted, config.upper_range[0], config.upper_range[1])
    ep_lower_shifted = _clamp_to_range(ep_lower_shifted, config.lower_range[0], config.lower_range[1])
    all_upper.extend(ep_upper_shifted)
    all_lower.extend(ep_lower_shifted)

    # --- Section 4: mm. 7-8 — Subject in lower (dominant) + countersubject in upper ---
    section4_onset = section3_onset + 2 * beats_per_measure
    section4_measure = section3_measure + 2

    # Subject in the dominant key in the lower voice
    dom_subject = generate_tonal_answer(subject_notes, key_tonic=config.key_tonic, mode=config.mode)
    lower_dom = _shift_notes(
        dom_subject, onset_offset=section4_onset, measure_offset=section4_measure,
        voice_id="Lower:1", transpose=-12, beats_per_measure=beats_per_measure,
    )
    lower_dom = _clamp_to_range(lower_dom, config.lower_range[0], config.lower_range[1])
    all_lower.extend(lower_dom)

    # Countersubject in upper
    cs2 = generate_countersubject(
        subject_notes, dom_subject, key_tonic=dom_key, mode=config.mode, rng=rng,
    )
    upper_cs2 = _shift_notes(
        cs2, onset_offset=section4_onset, measure_offset=section4_measure,
        voice_id="Upper:1", beats_per_measure=beats_per_measure,
    )
    upper_cs2 = _clamp_to_range(upper_cs2, config.upper_range[0], config.upper_range[1])
    all_upper.extend(upper_cs2)

    # --- Build EventGraph ---
    all_notes = all_upper + all_lower
    # Compute total measures
    max_measure = max((n.measure_number for n in all_notes), default=8)

    metadata = EncodingMetadata(
        encoding_id="invention-generated",
        work_id="bachbot-invention",
        title="Two-Part Invention (bachbot-study)",
        composer="bachbot",
        source_format="generated",
        key_estimate=KeyEstimate(tonic=config.key_tonic, mode=config.mode, confidence=1.0),
        meter=config.meter,
    )

    section = Section(
        section_id="invention-main",
        work_id="bachbot-invention",
        label="Invention",
        section_type="invention",
        measure_start=1,
        measure_end=max_measure,
    )

    voices = [
        Voice(
            voice_id="Upper:1",
            section_id="invention-main",
            normalized_voice_name="Upper",
            part_name="Upper",
            range_profile=config.upper_range,
        ),
        Voice(
            voice_id="Lower:1",
            section_id="invention-main",
            normalized_voice_name="Lower",
            part_name="Lower",
            range_profile=config.lower_range,
        ),
    ]

    return EventGraph(
        metadata=metadata,
        section=section,
        voices=voices,
        notes=all_notes,
    )


# ---------------------------------------------------------------------------
# CLI helper: parse subject string
# ---------------------------------------------------------------------------


def parse_subject_string(
    subject_str: str,
    *,
    voice_id: str = "Upper:1",
    beats_per_measure: float = 4.0,
    default_duration: float = 1.0,
) -> list[TypedNote]:
    """Parse a space-separated pitch string like 'C4 D4 E4 F4' into TypedNotes.

    Each pitch gets *default_duration* quarter-note length.
    """
    tokens = subject_str.strip().split()
    notes: list[TypedNote] = []
    onset = 0.0
    for token in tokens:
        midi = note_name_to_midi(token)
        measure = 1 + int(onset // beats_per_measure)
        beat = 1.0 + (onset % beats_per_measure)
        notes.append(
            TypedNote(
                pitch=token,
                midi=midi,
                duration_quarters=default_duration,
                offset_quarters=onset,
                measure_number=measure,
                beat=beat,
                voice_id=voice_id,
            )
        )
        onset += default_duration
    return notes
