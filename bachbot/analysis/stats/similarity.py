from __future__ import annotations

from math import sqrt

from bachbot.encodings.event_graph import EventGraph
from bachbot.features.pitch import pitch_class_histogram


def graph_similarity(left: EventGraph, right: EventGraph) -> float:
    left_hist = pitch_class_histogram(left)
    right_hist = pitch_class_histogram(right)
    distance = sqrt(sum((left_hist[index] - right_hist[index]) ** 2 for index in range(12)))
    return round(1 / (1 + distance), 4)

