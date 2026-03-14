"""AI/ML hypothesis rubric helpers."""

from __future__ import annotations


def hypothesis_score(measurability: float, formalizability: float, falsifiability: float) -> float:
    return round((measurability + formalizability + falsifiability) / 3, 3)
