from __future__ import annotations


def validate_fugue_constraints(*, voice_count: int, answer_type: str) -> dict[str, object]:
    return {
        "ok": voice_count >= 2 and answer_type in {"auto", "real", "tonal"},
        "voice_count": voice_count,
        "answer_type": answer_type,
    }

