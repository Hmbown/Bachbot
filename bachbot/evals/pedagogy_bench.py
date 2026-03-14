"""Pedagogy rubric helpers."""

from __future__ import annotations


def pedagogy_score(correctness: float, clarity: float, evidence_faithfulness: float) -> float:
    return round((correctness + clarity + evidence_faithfulness) / 3, 3)
