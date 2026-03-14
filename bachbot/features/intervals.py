"""Interval feature helpers."""

from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph


def melodic_intervals(graph: EventGraph, voice_id: str) -> list[int]:
    events = [event for event in graph.voice_events(voice_id) if event.pitch_midi is not None]
    return [
        later.pitch_midi - earlier.pitch_midi
        for earlier, later in zip(events, events[1:], strict=False)
        if earlier.pitch_midi is not None and later.pitch_midi is not None
    ]
