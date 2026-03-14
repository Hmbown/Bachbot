from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph
from bachbot.features.motif_vectors import motif_vector


def recurrence_map(graph: EventGraph, n: int = 3) -> dict[str, dict[str, object]]:
    recurrences: dict[str, dict[str, object]] = {}
    for voice_id in graph.ordered_voice_ids():
        events = graph.voice_events(voice_id)
        for index, vector in enumerate(motif_vector(graph, voice_id, n=n)):
            key = ",".join(str(item) for item in vector)
            window = events[index : index + n + 1]
            if len(window) < n + 1:
                continue
            payload = recurrences.setdefault(
                key,
                {
                    "pattern": vector,
                    "count": 0,
                    "occurrences": [],
                },
            )
            payload["count"] += 1
            payload["occurrences"].append(
                {
                    "voice_id": voice_id,
                    "start_index": index,
                    "end_index": index + n,
                    "start_onset": window[0].offset_quarters,
                    "end_onset": window[-1].offset_quarters + window[-1].duration_quarters,
                    "start_measure": window[0].measure_number,
                    "end_measure": window[-1].measure_number,
                }
            )
    for payload in recurrences.values():
        payload["occurrences"].sort(key=lambda item: (item["start_onset"], item["voice_id"]))
    return {label: payload for label, payload in recurrences.items() if payload["count"] > 1}
