"""Hypermeter helpers."""

from __future__ import annotations


def metric_strength(beat: float) -> str:
    if beat == 0:
        return "strong"
    if beat in {1.0, 2.0}:
        return "medium"
    return "weak"
