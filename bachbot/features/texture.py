"""Texture summaries."""

from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph


def average_active_voices(graph: EventGraph) -> float:
    onsets = list(graph.iter_onsets())
    if not onsets:
        return 0.0
    active_counts = [len(graph.active_pitches_at(onset)) for onset in onsets]
    return sum(active_counts) / len(active_counts)
