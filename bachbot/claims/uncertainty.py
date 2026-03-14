from __future__ import annotations

from bachbot.analysis.pipeline import AnalysisReport


def collect_uncertainties(report: AnalysisReport) -> list[str]:
    items: list[str] = []
    for event in report.harmony:
        if event.confidence < 0.6:
            items.append(f"Harmonic ambiguity at {event.ref_id}")
    return items
