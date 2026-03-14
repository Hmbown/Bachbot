from __future__ import annotations

from bachbot.analysis.harmony.cadence import summarize_harmony
from bachbot.encodings.event_graph import EventGraph


def build_tonal_graph(graph: EventGraph) -> list[tuple[str, str]]:
    events = summarize_harmony(graph)
    labels = [event.roman_numeral_candidate_set[0] if event.roman_numeral_candidate_set else "?" for event in events]
    return list(zip(labels, labels[1:]))

