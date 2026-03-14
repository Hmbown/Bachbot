"""Rhythmic feature helpers."""

from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph


def duration_histogram(graph: EventGraph) -> dict[float, int]:
    histogram: dict[float, int] = {}
    for event in graph.sorted_events():
        histogram[event.duration] = histogram.get(event.duration, 0) + 1
    return histogram


def onset_density(graph: EventGraph) -> float:
    duration = graph.total_duration()
    if duration == 0:
        return 0.0
    return len(list(graph.iter_onsets())) / duration


def onset_density_by_measure(graph: EventGraph) -> dict[int, float]:
    density: dict[int, float] = {}
    for measure, notes in graph.notes_by_measure().items():
        onsets = {note.offset_quarters for note in notes if not note.is_rest}
        duration = max((note.duration_quarters for note in notes), default=1.0)
        density[measure] = round(len(onsets) / max(duration, 1.0), 2)
    return density
