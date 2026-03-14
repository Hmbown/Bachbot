from __future__ import annotations


def validate_keyboard_constraints(*, max_span_semitones: int = 19) -> dict[str, object]:
    return {"ok": max_span_semitones <= 24, "max_span_semitones": max_span_semitones}

