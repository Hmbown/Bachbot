from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph
from bachbot.features.pitch import pitch_class_histogram
from bachbot.features.rhythm import onset_density_by_measure


def summarize_distributions(graph: EventGraph) -> dict[str, object]:
    return {
        "pitch_class_histogram": pitch_class_histogram(graph),
        "onset_density": onset_density_by_measure(graph),
    }

