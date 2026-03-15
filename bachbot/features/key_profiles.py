from __future__ import annotations

from bachbot.models.base import KeyEstimate, TypedNote

# Krumhansl-Kessler key profiles (Krumhansl, C. L. "Cognitive Foundations
# of Musical Pitch", Oxford University Press, 1990, Table 2.1).  These
# represent the perceived stability of each pitch class in a tonal context,
# derived from probe-tone experiments.  The correlation-based key-finding
# algorithm follows Krumhansl & Schmuckler.
MAJOR_TEMPLATE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_TEMPLATE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
PC_TO_NOTE = {
    0: "C",
    1: "C#",
    2: "D",
    3: "Eb",
    4: "E",
    5: "F",
    6: "F#",
    7: "G",
    8: "Ab",
    9: "A",
    10: "Bb",
    11: "B",
}
NOTE_TO_PC = {v: k for k, v in PC_TO_NOTE.items()}
NOTE_TO_PC.update({"Db": 1, "D#": 3, "Gb": 6, "G#": 8, "A#": 10, "Cb": 11})


def _correlate(histogram: list[float], template: list[float], shift: int) -> float:
    return sum(histogram[(index + shift) % 12] * template[index] for index in range(12))


def _confidence(best_score: float, total: float) -> float:
    if total == 0:
        return 0.5
    return round(min(0.99, 0.5 + (best_score / (total * 8))), 2)


def estimate_key_from_notes(
    notes: list[TypedNote],
    preferred_tonic: str | None = None,
    keysig: int | None = None,
) -> KeyEstimate:
    histogram = [0.0] * 12
    for note in notes:
        if note.midi is not None and not note.is_rest:
            histogram[note.midi % 12] += max(note.duration_quarters, 0.25)
    total = sum(histogram)

    if keysig is not None and preferred_tonic and preferred_tonic in NOTE_TO_PC:
        major_pc = NOTE_TO_PC[preferred_tonic]
        minor_pc = (major_pc - 3) % 12
        major_score = _correlate(histogram, MAJOR_TEMPLATE, major_pc)
        minor_score = _correlate(histogram, MINOR_TEMPLATE, minor_pc)
        if minor_score > major_score:
            return KeyEstimate(tonic=PC_TO_NOTE[minor_pc], mode="minor", confidence=_confidence(minor_score, total))
        return KeyEstimate(tonic=preferred_tonic, mode="major", confidence=_confidence(major_score, total))

    best_shift = 0
    best_mode = "major"
    best_score = float("-inf")
    for shift in range(12):
        for mode, template in (("major", MAJOR_TEMPLATE), ("minor", MINOR_TEMPLATE)):
            score = _correlate(histogram, template, shift)
            if preferred_tonic and PC_TO_NOTE[shift] == preferred_tonic:
                score += 1.5
            if score > best_score:
                best_score = score
                best_shift = shift
                best_mode = mode
    return KeyEstimate(tonic=PC_TO_NOTE[best_shift], mode=best_mode, confidence=_confidence(best_score, total))


def estimate_key(graph) -> str:
    notes = getattr(graph, "notes", None)
    if notes is None:
        notes = getattr(graph, "events", [])
    return estimate_key_from_notes(notes).tonic

