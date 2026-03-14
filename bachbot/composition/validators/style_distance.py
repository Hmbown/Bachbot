from __future__ import annotations

from bachbot.analysis.stats.similarity import graph_similarity
from bachbot.encodings.event_graph import EventGraph


def average_style_distance(graph: EventGraph, references: list[EventGraph]) -> float:
    if not references:
        return 0.0
    scores = [graph_similarity(graph, reference) for reference in references]
    return round(sum(scores) / len(scores), 4)

