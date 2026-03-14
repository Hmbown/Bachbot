"""Information-theoretic summaries."""

from __future__ import annotations

import math

from bachbot.encodings.event_graph import EventGraph
from .pitch import pitch_class_histogram


def pitch_entropy(graph: EventGraph) -> float:
    histogram = pitch_class_histogram(graph)
    total = sum(histogram.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in histogram.values():
        if count == 0:
            continue
        probability = count / total
        entropy -= probability * math.log2(probability)
    return entropy
