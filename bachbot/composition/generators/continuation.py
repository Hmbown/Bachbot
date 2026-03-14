from __future__ import annotations

from bachbot.composition.generators.pattern_fill import harmonize_chorale_melody
from bachbot.encodings.event_graph import EventGraph


def generate_continuation_candidates(fragment_graph: EventGraph, branches: int = 2) -> list[tuple[EventGraph, list[str]]]:
    candidates: list[tuple[EventGraph, list[str]]] = []
    for index in range(branches):
        graph, trace = harmonize_chorale_melody(fragment_graph, artifact_id=f"CONT-{index + 1:03d}")
        trace.append("Continuation boundary is explicit; this is a Bachbot hypothesis, not a source claim.")
        candidates.append((graph, trace))
    return candidates

