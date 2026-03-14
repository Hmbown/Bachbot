from __future__ import annotations

from bachbot.analysis.form.recurrence import recurrence_map
from bachbot.encodings.event_graph import EventGraph


def detect_countersubjects(graph: EventGraph) -> list[dict[str, object]]:
    recurrences = recurrence_map(graph, n=4)
    return [
        {
            "label": label,
            "pattern": payload["pattern"],
            "count": payload["count"],
            "voices": sorted({occurrence["voice_id"] for occurrence in payload["occurrences"]}),
            "occurrences": payload["occurrences"],
            "type": "possible_countersubject",
        }
        for label, payload in recurrences.items()
        if payload["count"] >= 2 and len({occurrence["voice_id"] for occurrence in payload["occurrences"]}) >= 2
    ]
