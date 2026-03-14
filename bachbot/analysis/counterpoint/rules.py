from __future__ import annotations

from bachbot.analysis.counterpoint.dissonance import detect_suspensions
from bachbot.analysis.counterpoint.voiceleading import detect_parallels, detect_voice_crossings
from bachbot.encodings.event_graph import EventGraph


def analyze_counterpoint(graph: EventGraph) -> dict[str, object]:
    parallels = detect_parallels(graph)
    crossings = detect_voice_crossings(graph)
    suspensions = detect_suspensions(graph)
    return {
        "parallel_5ths": len([item for item in parallels if item["type"] == "parallel_5ths"]),
        "parallel_8ves": len([item for item in parallels if item["type"] == "parallel_8ves"]),
        "suspensions": len(suspensions),
        "issues": parallels + crossings,
        "suspension_details": suspensions,
    }

