"""Pitch feature helpers."""

from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph


def pitch_class_histogram(graph: EventGraph) -> dict[int, int]:
    histogram = {index: 0 for index in range(12)}
    for event in graph.pitch_events():
        histogram[event.pitch_midi % 12] += 1
    return histogram


def ambitus(graph: EventGraph, voice_id: str | None = None) -> tuple[int, int] | None:
    events = graph.pitch_events() if voice_id is None else graph.voice_events(voice_id)
    pitches = [event.pitch_midi for event in events if event.pitch_midi is not None]
    if not pitches:
        return None
    return min(pitches), max(pitches)
