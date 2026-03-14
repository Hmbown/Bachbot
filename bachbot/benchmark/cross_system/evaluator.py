"""Cross-system comparison evaluator: compute quality metrics and generate reports."""

from __future__ import annotations

from collections import defaultdict

from pydantic import Field

from bachbot.analysis.chorale.satb import analyze_chorale_texture
from bachbot.benchmark.cross_system.adapters import SystemAdapter
from bachbot.benchmark.cross_system.test_set import BenchmarkMelody
from bachbot.benchmark.protocol import VOICE_NORMALIZE, extract_voice_notes
from bachbot.composition.validators.hard_rules import validate_graph
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import BachbotModel


# ── Score models ─────────────────────────────────────────────────────

class SystemScore(BachbotModel):
    """Quality metrics for a single harmonization by a system on one melody."""

    system_name: str
    melody_id: str
    parallel_violations: int = 0
    voice_crossing_count: int = 0
    chord_variety: float = 0.0
    voice_leading_smoothness: float = 0.0  # avg interval size in semitones
    spacing_violations: int = 0
    overall_score: float = 0.0


class ComparisonReport(BachbotModel):
    """Aggregated comparison of multiple systems across the test set."""

    test_set_name: str
    melody_count: int
    systems: list[str]
    scores: list[SystemScore] = Field(default_factory=list)
    summary: dict[str, dict[str, float]] = Field(default_factory=dict)


# ── Metric computation ───────────────────────────────────────────────

def _count_parallel_violations(graph: EventGraph) -> int:
    """Count parallel 5ths and 8ves violations."""
    report = validate_graph(graph)
    return sum(
        1 for issue in report.issues
        if issue.code in ("parallel_5ths", "parallel_8ves")
    )


def _count_spacing_violations(graph: EventGraph) -> int:
    """Count SATB spacing violations from texture analysis."""
    texture = analyze_chorale_texture(graph)
    return len(texture.get("spacing_issues", []))


def _count_voice_crossings(graph: EventGraph) -> int:
    """Count voice crossing events."""
    texture = analyze_chorale_texture(graph)
    return len(texture.get("crossing_issues", []))


def _chord_variety(graph: EventGraph) -> float:
    """Number of unique pitch-class sets across all onsets."""
    pc_sets: set[tuple[int, ...]] = set()
    for onset in graph.iter_onsets():
        active = graph.active_pitches_at(onset)
        if active:
            pcs = tuple(sorted({n.midi % 12 for n in active if n.midi is not None}))
            if pcs:
                pc_sets.add(pcs)
    return float(len(pc_sets))


def _voice_leading_smoothness(graph: EventGraph) -> float:
    """Average absolute interval size across all voice parts (lower = smoother)."""
    total_intervals = 0
    total_count = 0
    for role in ("soprano", "alto", "tenor", "bass"):
        notes = extract_voice_notes(graph, role)
        midis = [n.midi for n in notes if n.midi is not None]
        if len(midis) < 2:
            continue
        for a, b in zip(midis, midis[1:]):
            total_intervals += abs(b - a)
            total_count += 1
    if total_count == 0:
        return 0.0
    return total_intervals / total_count


def evaluate_harmonization(graph: EventGraph, system_name: str = "", melody_id: str = "") -> SystemScore:
    """Compute quality metrics for a single harmonization."""
    parallel = _count_parallel_violations(graph)
    spacing = _count_spacing_violations(graph)
    crossings = _count_voice_crossings(graph)
    variety = _chord_variety(graph)
    smoothness = _voice_leading_smoothness(graph)

    # Overall score: higher is better.
    # Reward variety and smoothness; penalize violations.
    # Smoothness inverted: lower raw smoothness = better (stepwise).
    smoothness_score = max(0.0, 1.0 - smoothness / 12.0)  # 12 semitone = octave
    variety_score = min(1.0, variety / 15.0)  # 15 unique chords = full marks
    penalty = 0.05 * parallel + 0.03 * spacing + 0.02 * crossings
    overall = max(0.0, 0.5 * variety_score + 0.5 * smoothness_score - penalty)

    return SystemScore(
        system_name=system_name,
        melody_id=melody_id,
        parallel_violations=parallel,
        voice_crossing_count=crossings,
        chord_variety=round(variety, 1),
        voice_leading_smoothness=round(smoothness, 3),
        spacing_violations=spacing,
        overall_score=round(overall, 4),
    )


# ── Multi-system comparison ──────────────────────────────────────────

def compare_systems(
    test_set: list[BenchmarkMelody],
    adapters: list[SystemAdapter],
) -> ComparisonReport:
    """Run all adapters on all melodies, compute comparative scores."""
    system_names = [a.name for a in adapters]
    all_scores: list[SystemScore] = []

    for melody in test_set:
        for adapter in adapters:
            if not adapter.is_available():
                continue
            graph = adapter.harmonize(melody)
            if graph is None:
                # Record zero score on failure.
                all_scores.append(SystemScore(
                    system_name=adapter.name,
                    melody_id=melody.melody_id,
                ))
                continue
            score = evaluate_harmonization(graph, system_name=adapter.name, melody_id=melody.melody_id)
            all_scores.append(score)

    # Compute per-system summaries.
    by_system: dict[str, list[SystemScore]] = defaultdict(list)
    for s in all_scores:
        by_system[s.system_name].append(s)

    summary: dict[str, dict[str, float]] = {}
    for sys_name, scores in by_system.items():
        n = len(scores)
        if n == 0:
            continue
        summary[sys_name] = {
            "melody_count": float(n),
            "avg_parallel_violations": round(sum(s.parallel_violations for s in scores) / n, 2),
            "avg_voice_crossing_count": round(sum(s.voice_crossing_count for s in scores) / n, 2),
            "avg_chord_variety": round(sum(s.chord_variety for s in scores) / n, 1),
            "avg_voice_leading_smoothness": round(sum(s.voice_leading_smoothness for s in scores) / n, 3),
            "avg_spacing_violations": round(sum(s.spacing_violations for s in scores) / n, 2),
            "avg_overall_score": round(sum(s.overall_score for s in scores) / n, 4),
        }

    return ComparisonReport(
        test_set_name="standard-30",
        melody_count=len(test_set),
        systems=system_names,
        scores=all_scores,
        summary=summary,
    )


# ── Pretty-print ─────────────────────────────────────────────────────

def generate_comparison_table(report: ComparisonReport) -> str:
    """Pretty-print a comparison table from a ComparisonReport."""
    if not report.summary:
        return "No results to display."

    headers = [
        "System",
        "Melodies",
        "Parallels",
        "Crossings",
        "Spacing",
        "Variety",
        "Smoothness",
        "Overall",
    ]
    rows: list[list[str]] = [headers]

    for sys_name in sorted(report.summary):
        s = report.summary[sys_name]
        rows.append([
            sys_name,
            str(int(s.get("melody_count", 0))),
            f"{s.get('avg_parallel_violations', 0):.2f}",
            f"{s.get('avg_voice_crossing_count', 0):.2f}",
            f"{s.get('avg_spacing_violations', 0):.2f}",
            f"{s.get('avg_chord_variety', 0):.1f}",
            f"{s.get('avg_voice_leading_smoothness', 0):.3f}",
            f"{s.get('avg_overall_score', 0):.4f}",
        ])

    # Compute column widths.
    col_widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    separator = "  ".join("-" * w for w in col_widths)

    lines: list[str] = []
    lines.append("  ".join(cell.ljust(w) for cell, w in zip(rows[0], col_widths)))
    lines.append(separator)
    for row in rows[1:]:
        lines.append("  ".join(cell.ljust(w) for cell, w in zip(row, col_widths)))

    return "\n".join(lines)
