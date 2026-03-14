"""Search-based helper routines."""

from __future__ import annotations


def choose_closest(candidates: list[int], target: int) -> int:
    return min(candidates, key=lambda value: abs(value - target))
