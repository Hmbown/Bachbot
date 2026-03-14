from __future__ import annotations

from bachbot.features.intervals import melodic_intervals
from bachbot.encodings.event_graph import EventGraph


def contour_signature(graph: EventGraph, voice_id: str) -> str:
    signs = []
    for interval in melodic_intervals(graph, voice_id):
        if interval > 0:
            signs.append("U")
        elif interval < 0:
            signs.append("D")
        else:
            signs.append("S")
    return "".join(signs)

