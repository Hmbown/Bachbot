from __future__ import annotations

from bachbot.analysis.pipeline import AnalysisReport


def score_analysis_report(report: AnalysisReport) -> dict[str, object]:
    score = 0.0
    if report.harmony:
        score += 0.3
    if report.cadences:
        score += 0.3
    if report.voice_leading:
        score += 0.2
    if report.phrase_endings or report.fugue:
        score += 0.2
    return {"score": round(score, 2), "has_harmony": bool(report.harmony), "has_cadences": bool(report.cadences)}

