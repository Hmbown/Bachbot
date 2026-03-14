from __future__ import annotations


def validate_canon_constraints(*, delay_beats: int, interval_of_imitation: str) -> dict[str, object]:
    return {
        "ok": delay_beats > 0 and bool(interval_of_imitation),
        "delay_beats": delay_beats,
        "interval_of_imitation": interval_of_imitation,
    }

