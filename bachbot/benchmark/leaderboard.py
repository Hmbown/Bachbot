"""Leaderboard formatting for BachBench results."""

from __future__ import annotations

import json
from pathlib import Path

from bachbot.benchmark.protocol import SuiteResult


def format_leaderboard(suite: SuiteResult) -> dict:
    """Convert SuiteResult to leaderboard JSON schema."""
    scores: dict[str, dict[str, float]] = {}
    for task_name, summary in suite.task_summaries.items():
        scores[task_name] = {k: v for k, v in summary.items()}

    # Overall composite: mean of per-task composites
    composites = [s.get("composite", 0.0) for s in scores.values()]
    overall = sum(composites) / len(composites) if composites else 0.0

    return {
        "schema_version": "1.0.0",
        "submission": {
            "solver_name": suite.solver_name,
            "suite_version": suite.suite_version,
            "timestamp": suite.timestamp,
            "split": suite.split,
            "corpus_size": suite.corpus_size,
        },
        "scores": scores,
        "composite_score": round(overall, 4),
    }


def print_leaderboard(suite: SuiteResult) -> str:
    """Pretty-print leaderboard as text table."""
    lines = [
        f"BachBench Results — {suite.solver_name}",
        f"Split: {suite.split} | Corpus: {suite.corpus_size} chorales",
        f"{'─' * 60}",
    ]

    for task_name, summary in sorted(suite.task_summaries.items()):
        lines.append(f"\n  {task_name}:")
        for metric, value in sorted(summary.items()):
            lines.append(f"    {metric:30s} {value:>8.4f}")

    composites = [s.get("composite", 0.0) for s in suite.task_summaries.values()]
    overall = sum(composites) / len(composites) if composites else 0.0
    lines.append(f"\n{'─' * 60}")
    lines.append(f"  Overall composite: {overall:.4f}")

    return "\n".join(lines)


def export_leaderboard(suite: SuiteResult, output: Path) -> None:
    """Write leaderboard JSON to file."""
    lb = format_leaderboard(suite)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(lb, indent=2), encoding="utf-8")
