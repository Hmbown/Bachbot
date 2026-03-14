from __future__ import annotations

from bachbot.analysis.form.recurrence import recurrence_map
from bachbot.encodings.event_graph import EventGraph


def build_motif_graph(graph: EventGraph) -> dict[str, list[str]]:
    recurrences = recurrence_map(graph)
    motif_graph: dict[str, list[str]] = {}
    for label, payload in recurrences.items():
        for occurrence in payload["occurrences"]:
            voice = occurrence["voice_id"]
            motif_graph.setdefault(voice, [])
            if label not in motif_graph[voice]:
                motif_graph[voice].append(label)
    return motif_graph
