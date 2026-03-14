"""Motivic feature vectors."""

from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph
from .intervals import melodic_intervals


def motif_vector(graph: EventGraph, voice_id: str, n: int = 4) -> list[tuple[int, ...]]:
    intervals = melodic_intervals(graph, voice_id)
    return [tuple(intervals[index : index + n]) for index in range(max(len(intervals) - n + 1, 0))]
