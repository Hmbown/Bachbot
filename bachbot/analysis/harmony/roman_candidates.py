from __future__ import annotations

from bachbot.encodings.event_graph import VerticalitySlice
from bachbot.models.base import KeyEstimate
from bachbot.models.harmonic_event import HarmonicEvent

NOTE_TO_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
MAJOR = {"I": {0, 4, 7}, "ii": {2, 5, 9}, "iii": {4, 7, 11}, "IV": {5, 9, 0}, "V": {7, 11, 2}, "vi": {9, 0, 4}, "vii°": {11, 2, 5}}
MINOR = {"i": {0, 3, 7}, "ii°": {2, 5, 8}, "III": {3, 7, 10}, "iv": {5, 8, 0}, "V": {7, 11, 2}, "VI": {8, 0, 3}, "VII": {10, 2, 5}}
_DEGREE_ROOTS_MAJOR = {"I": 0, "ii": 2, "iii": 4, "IV": 5, "V": 7, "vi": 9, "vii°": 11}
_DEGREE_ROOTS_MINOR = {"i": 0, "ii°": 2, "III": 3, "iv": 5, "V": 7, "VI": 8, "VII": 10}
_DEGREE_ROOTS = {**_DEGREE_ROOTS_MAJOR, **_DEGREE_ROOTS_MINOR}
_MAJOR_SCALE_PCS = frozenset({0, 2, 4, 5, 7, 9, 11})
_MINOR_SCALE_PCS = frozenset({0, 2, 3, 5, 7, 8, 10})
MAJOR_7TH = {"V7": {7, 11, 2, 5}, "viiø7": {11, 2, 5, 9}, "ii7": {2, 5, 9, 0}, "IV7": {5, 9, 0, 4}, "vi7": {9, 0, 4, 7}}
MINOR_7TH = {"V7": {7, 11, 2, 5}, "viio7": {11, 2, 5, 8}, "iiø7": {2, 5, 8, 0}, "iv7": {5, 8, 0, 3}, "VI7": {8, 0, 3, 7}}

# Chromatic harmonies that Bach uses routinely.  Their absence from the
# diatonic-only palette is the primary driver of the chord-variety gap
# (generated ~4.3 distinct chords per chorale vs ~14.7 in the originals).
# All intervals are relative to the local tonic, matching the diatonic dicts.
CHROMATIC_MAJOR = {
    "N6": {1, 5, 8},        # Neapolitan (bII): Db-F-Ab in C
    "bVI": {8, 0, 3},       # borrowed from parallel minor
    "bVII": {10, 2, 5},     # borrowed from parallel minor
    "bIII": {3, 7, 10},     # borrowed from parallel minor
    "iv": {5, 8, 0},        # borrowed subdominant
}
CHROMATIC_MINOR = {
    "N6": {1, 5, 8},        # Neapolitan (bII): Db-F-Ab in C
    "III+": {3, 7, 11},     # augmented III from melodic minor ascending
}
# Augmented sixth chords resolve to V and appear in both modes.
AUGMENTED_SIXTHS = {
    "It+6": {8, 0, 6},      # Italian: Ab-C-F# in C
    "Fr+6": {8, 0, 2, 6},   # French: Ab-C-D-F# in C
    "Ger+6": {8, 0, 3, 6},  # German: Ab-C-Eb-F# in C
}

PC_TO_NOTE = {0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F", 6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}


def candidate_roman_numerals(slice_: VerticalitySlice, key: KeyEstimate) -> list[str]:
    tonic_pc = NOTE_TO_PC[key.tonic]
    pcs = {(pc - tonic_pc) % 12 for pc in slice_.pitch_classes}
    families = MAJOR if key.mode == "major" else MINOR
    sevenths = MAJOR_7TH if key.mode == "major" else MINOR_7TH
    chromatic = CHROMATIC_MAJOR if key.mode == "major" else CHROMATIC_MINOR
    n_pcs = len(pcs)
    ranked = []
    for label, chord_pcs in sevenths.items():
        overlap = len(pcs & chord_pcs)
        if overlap >= 3:
            # Only prefer seventh over triad when 4+ PCs are sounding
            bonus = 2 if n_pcs >= 4 and overlap == 4 else -3
            ranked.append((overlap * 4 - len(pcs - chord_pcs) + bonus, label))
    for label, triad in families.items():
        overlap = len(pcs & triad)
        if overlap >= 2:
            ranked.append((overlap * 4 - len(pcs - triad), label))
    # Chromatic / borrowed chords (small penalty to prefer diatonic readings)
    for label, chord_pcs in chromatic.items():
        overlap = len(pcs & chord_pcs)
        if overlap >= 2:
            ranked.append((overlap * 4 - len(pcs - chord_pcs) - 2, label))
    # Augmented sixth chords (both modes; very distinctive sonority)
    for label, chord_pcs in AUGMENTED_SIXTHS.items():
        overlap = len(pcs & chord_pcs)
        if overlap >= len(chord_pcs) - 1:
            ranked.append((overlap * 4 - len(pcs - chord_pcs) - 1, label))
    ranked.sort(reverse=True)
    return [label for _, label in ranked[:3]]


def _classify_verticality(pcs: set[int], n_candidates: int) -> str:
    n = len(pcs)
    if n == 3:
        return "triad"
    if n == 4 and n_candidates > 0:
        return "seventh"
    return "verticality"


def estimate_local_key(slices: list[VerticalitySlice], center: int, global_key: KeyEstimate, window_beats: float = 8.0) -> KeyEstimate:
    """Windowed key estimation for modulation tracking.

    Returns global_key unchanged when there are too few slices for
    meaningful windowed estimation (< 8 slices).
    """
    if len(slices) < 8:
        return global_key

    from bachbot.features.key_profiles import MAJOR_TEMPLATE, MINOR_TEMPLATE, PC_TO_NOTE as KP_PC_TO_NOTE, _correlate

    histogram = [0.0] * 12
    center_onset = slices[center].onset
    for s in slices:
        if abs(s.onset - center_onset) <= window_beats:
            for note in s.active_notes:
                if note.midi is not None and not note.is_rest:
                    histogram[note.midi % 12] += max(note.duration_quarters, 0.25)
    if sum(histogram) == 0:
        return global_key
    best_shift = NOTE_TO_PC[global_key.tonic]
    best_mode = global_key.mode
    best_score = float("-inf")
    for shift in range(12):
        for mode, template in (("major", MAJOR_TEMPLATE), ("minor", MINOR_TEMPLATE)):
            score = _correlate(histogram, template, shift)
            if KP_PC_TO_NOTE[shift] == global_key.tonic and mode == global_key.mode:
                score += 2.0
            if score > best_score:
                best_score = score
                best_shift = shift
                best_mode = mode
    return KeyEstimate(tonic=KP_PC_TO_NOTE[best_shift], mode=best_mode, confidence=round(min(0.95, best_score / max(sum(histogram) * 4, 1)), 2))


def _best_chord_pcs(candidates: list[str], key: KeyEstimate) -> set[int]:
    """Return the pitch class set of the top-ranked candidate chord.

    Handles secondary dominant labels (e.g., ``V/V``), chromatic chords
    (Neapolitan, augmented sixths, modal mixture), by computing their PCs
    dynamically so that ``tag_nonharmonic_tones`` can correctly classify
    NCTs for any recognized harmony.
    """
    if not candidates:
        return set()
    label = candidates[0]
    families = MAJOR if key.mode == "major" else MINOR
    sevenths = MAJOR_7TH if key.mode == "major" else MINOR_7TH
    chromatic = CHROMATIC_MAJOR if key.mode == "major" else CHROMATIC_MINOR
    chord_pcs = sevenths.get(label) or families.get(label) or chromatic.get(label) or AUGMENTED_SIXTHS.get(label)
    if chord_pcs is not None:
        return chord_pcs
    # Try secondary dominant resolution — use target_root_rel directly so
    # returned PCs are relative to the key tonic (matching MAJOR/MINOR convention)
    if "/" in label:
        quality, target = label.split("/", 1)
        target_root_rel = _DEGREE_ROOTS.get(target)
        if target_root_rel is not None:
            for prefix, template_pcs in _secondary_dom_templates(target_root_rel):
                if prefix == quality:
                    return template_pcs
    return set()


def tag_nonharmonic_tones(
    slices: list[VerticalitySlice],
    events: list[HarmonicEvent],
    key: KeyEstimate,
) -> None:
    """Tag nonharmonic tones on each HarmonicEvent in-place.

    Classification heuristics:
    - suspension: note was present in previous slice and resolves down by step
    - passing_tone: stepwise between previous and next notes in the same voice
    - neighbor_tone: step away from and back to the same pitch
    - nct: unclassified non-chord tone
    """
    for idx, (slice_, event) in enumerate(zip(slices, events)):
        # Use local key when available — candidates are computed relative to it
        if event.local_key:
            parts = event.local_key.split()
            local_tonic = parts[0] if parts else key.tonic
            local_mode = parts[1] if len(parts) > 1 else key.mode
            effective_key = KeyEstimate(tonic=local_tonic, mode=local_mode)
        else:
            effective_key = key
        effective_key_tonic = NOTE_TO_PC.get(effective_key.tonic, 0)
        chord_pcs = _best_chord_pcs(event.roman_numeral_candidate_set, effective_key)
        if not chord_pcs:
            continue
        tags: list[str] = []
        for note in slice_.active_notes:
            if note.midi is None or note.is_rest:
                continue
            relative_pc = (note.midi % 12 - effective_key_tonic) % 12
            if relative_pc in chord_pcs:
                continue
            # Non-chord tone found — classify it
            pc_name = PC_TO_NOTE.get(note.midi % 12, str(note.midi % 12))
            # Check for suspension: note tied/repeated from previous slice
            if idx > 0 and (note.tie_stop or any(
                prev.midi == note.midi for prev in slices[idx - 1].active_notes
                if prev.midi is not None and prev.voice_id == note.voice_id
            )):
                tags.append(f"SUS:{pc_name}")
            # Check for passing/neighbor: step from prev, step to next in same voice
            elif idx > 0 and idx < len(slices) - 1:
                prev_notes = [n for n in slices[idx - 1].active_notes if n.voice_id == note.voice_id and n.midi is not None]
                next_notes = [n for n in slices[idx + 1].active_notes if n.voice_id == note.voice_id and n.midi is not None]
                prev_midi = prev_notes[0].midi if prev_notes else None
                next_midi = next_notes[0].midi if next_notes else None
                if prev_midi is not None and next_midi is not None:
                    step_from = abs(note.midi - prev_midi) <= 2
                    step_to = abs(note.midi - next_midi) <= 2
                    if step_from and step_to and prev_midi == next_midi:
                        tags.append(f"NT:{pc_name}")
                    elif step_from and step_to:
                        tags.append(f"PT:{pc_name}")
                    else:
                        tags.append(f"NCT:{pc_name}")
                else:
                    tags.append(f"NCT:{pc_name}")
            else:
                tags.append(f"NCT:{pc_name}")
        event.nonharmonic_tone_tags = tags


def harmonic_event_from_slice(
    slice_: VerticalitySlice,
    key: KeyEstimate,
    encoding_id: str,
    local_key: KeyEstimate | None = None,
) -> HarmonicEvent:
    effective_key = local_key or key
    candidates = candidate_roman_numerals(slice_, effective_key)
    tonic_pc = NOTE_TO_PC[effective_key.tonic]
    pcs = {(pc - tonic_pc) % 12 for pc in slice_.pitch_classes}
    return HarmonicEvent(
        harmonic_event_id=f"{encoding_id}:h{slice_.measure_number}:{int(slice_.onset * 100)}",
        ref_id=f"{encoding_id}:m{slice_.measure_number}",
        onset=slice_.onset,
        duration=slice_.duration,
        verticality_class=_classify_verticality(pcs, len(candidates)),
        local_key=f"{effective_key.tonic} {effective_key.mode}",
        global_key=f"{key.tonic} {key.mode}",
        roman_numeral_candidate_set=candidates,
        figured_bass_like_summary=slice_.bass_note.pitch if slice_.bass_note else None,
        confidence=round(min(0.25 + 0.2 * len(candidates), 0.95), 2),
        method="rule",
    )


def _secondary_dom_templates(target_root_abs: int) -> list[tuple[str, set[int]]]:
    """Return (quality_prefix, pitch_class_set) for V, V7, viio7 of a target root."""
    dr = (target_root_abs + 7) % 12
    lt = (target_root_abs + 11) % 12
    return [
        ("V7", {dr, (dr + 4) % 12, (dr + 7) % 12, (dr + 10) % 12}),
        ("V", {dr, (dr + 4) % 12, (dr + 7) % 12}),
        ("viio7", {lt, (lt + 3) % 12, (lt + 6) % 12, (lt + 9) % 12}),
    ]


def detect_secondary_dominants(
    events: list[HarmonicEvent],
    slices: list["VerticalitySlice"],
    key: KeyEstimate,
) -> None:
    """Detect secondary dominants by comparing consecutive events.

    For each pair (event[i], event[i+1]), checks if event[i]'s pitch classes
    match V, V7, or viio7 of event[i+1]'s root. Requires at least one chromatic
    pitch (not in the local scale) that belongs to the secondary dominant template.
    Prepends the label (e.g., ``V/V``) to ``roman_numeral_candidate_set`` in-place.
    """
    tonic_pc = NOTE_TO_PC.get(key.tonic, 0)

    for i in range(len(events) - 1):
        next_candidates = events[i + 1].roman_numeral_candidate_set
        if not next_candidates:
            continue
        target_label = next_candidates[0]
        target_root_rel = _DEGREE_ROOTS.get(target_label)
        if target_root_rel is None or target_label in ("I", "i"):
            continue  # V/I is just V

        # Use local key for scale membership check
        local_key_str = events[i].local_key
        if local_key_str:
            parts = local_key_str.split()
            local_tonic_pc = NOTE_TO_PC.get(parts[0], tonic_pc)
            local_mode = parts[1] if len(parts) > 1 else key.mode
        else:
            local_tonic_pc = tonic_pc
            local_mode = key.mode

        local_scale = _MAJOR_SCALE_PCS if local_mode == "major" else _MINOR_SCALE_PCS
        key_pcs = frozenset((local_tonic_pc + pc) % 12 for pc in local_scale)

        actual_pcs = set(slices[i].pitch_classes)
        chromatic_pcs = actual_pcs - key_pcs
        if not chromatic_pcs:
            continue

        target_root_abs = (local_tonic_pc + target_root_rel) % 12
        templates = _secondary_dom_templates(target_root_abs)

        best_label: str | None = None
        best_score = 0
        for prefix, template_pcs in templates:
            overlap = len(actual_pcs & template_pcs)
            if overlap >= 3 and (chromatic_pcs & template_pcs):
                # Penalize both extra actual PCs and missing template PCs
                score = overlap * 4 - len(actual_pcs - template_pcs) - len(template_pcs - actual_pcs)
                if score > best_score:
                    best_score = score
                    best_label = f"{prefix}/{target_label}"

        if best_label:
            events[i].roman_numeral_candidate_set.insert(0, best_label)

