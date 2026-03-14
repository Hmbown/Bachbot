from __future__ import annotations

from statistics import mean

from bachbot.analysis.stats.distributions import summarize_distributions
from bachbot.encodings.event_graph import EventGraph


def measure_anomaly_scores(graph: EventGraph) -> dict[int, float]:
    density = summarize_distributions(graph)["onset_density"]
    average = mean(density.values()) if density else 0.0
    return {measure: round(abs(count - average), 2) for measure, count in density.items()}

