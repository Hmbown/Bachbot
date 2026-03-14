from __future__ import annotations

from bachbot.encodings.event_graph import VerticalitySlice
from bachbot.models.base import KeyEstimate

NOTE_TO_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}


def _normalize_key(key: KeyEstimate | str) -> KeyEstimate:
    return key if isinstance(key, KeyEstimate) else KeyEstimate(tonic=key, mode="major", confidence=0.5)


def degree_for_pitch_class(pitch_class: int, key: KeyEstimate | str) -> str | None:
    normalized = _normalize_key(key)
    relative = (pitch_class - NOTE_TO_PC[normalized.tonic]) % 12
    mapping = {0: "1", 2: "2", 4: "3", 5: "4", 7: "5", 9: "6", 11: "7"} if normalized.mode == "major" else {0: "1", 2: "2", 3: "3", 5: "4", 7: "5", 8: "6", 10: "7"}
    return mapping.get(relative)


def extract_formula(previous: VerticalitySlice, current: VerticalitySlice, *, kind: str, key: KeyEstimate | str) -> str | None:
    attr = "bass_note" if kind == "bass" else "soprano_note"
    left = getattr(previous, attr)
    right = getattr(current, attr)
    if left is None or right is None or left.midi is None or right.midi is None:
        return None
    left_degree = degree_for_pitch_class(left.midi % 12, key)
    right_degree = degree_for_pitch_class(right.midi % 12, key)
    return f"{left_degree}-{right_degree}" if left_degree and right_degree else None

