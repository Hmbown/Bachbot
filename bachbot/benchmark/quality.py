"""Quality evaluation for generated chorales against Bach corpus statistics."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from pydantic import Field

from bachbot.analysis.chorale.satb import analyze_chorale_texture
from bachbot.analysis.harmony.cadence import detect_cadences, summarize_harmony
from bachbot.analysis.rhythm.harmonic_rhythm import extract_harmonic_rhythm
from bachbot.benchmark.complexity import (
    DEFAULT_COMPLEXITY_STATS_PATH,
    ComplexityCorpusStats,
    MetricSummary,
    compare_profile_to_corpus,
    complexity_divergence,
    compute_complexity,
    load_or_compute_corpus_stats,
)
from bachbot.benchmark.metrics import harmonic_similarity
from bachbot.composition.validators.hard_rules import validate_graph
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import BachbotModel

DEFAULT_QUALITY_STATS_PATH = Path("data/derived/quality_corpus_stats.json")
_QUALITY_SCALAR_FIELDS = (
    "chord_variety",
    "harmonic_rhythm_mean",
    "nonharmonic_tone_density",
    "contrary_motion_ratio",
    "parallel_violation_rate",
)


class QualityCorpusStats(BachbotModel):
    graph_count: int
    complexity: ComplexityCorpusStats
    chord_distribution: dict[str, float] = Field(default_factory=dict)
    cadence_distribution: dict[str, float] = Field(default_factory=dict)
    metric_summaries: dict[str, MetricSummary] = Field(default_factory=dict)


class QualityReport(BachbotModel):
    work_id: str
    bach_fidelity_score: float
    metrics: dict[str, float] = Field(default_factory=dict)
    passed_validation: bool


def compute_quality_corpus_stats(
    graphs: list[EventGraph],
    *,
    complexity_stats: ComplexityCorpusStats | None = None,
) -> QualityCorpusStats:
    chord_counts: Counter[str] = Counter()
    cadence_counts: Counter[str] = Counter()
    scalar_values = {field: [] for field in _QUALITY_SCALAR_FIELDS}

    for graph in graphs:
        snapshot = _quality_snapshot(graph)
        chord_counts.update(snapshot["chord_counts"])
        cadence_counts.update(snapshot["cadence_counts"])
        for field in _QUALITY_SCALAR_FIELDS:
            scalar_values[field].append(float(snapshot[field]))

    metric_summaries = {
        field: MetricSummary(
            mean=round(_mean(values), 4),
            std=round(_stddev(values), 4),
        )
        for field, values in scalar_values.items()
    }
    return QualityCorpusStats(
        graph_count=len(graphs),
        complexity=complexity_stats or compute_quality_corpus_stats_complexity(graphs),
        chord_distribution=_normalize_counter(chord_counts),
        cadence_distribution=_normalize_counter(cadence_counts),
        metric_summaries=metric_summaries,
    )


def compute_quality_corpus_stats_complexity(graphs: list[EventGraph]) -> ComplexityCorpusStats:
    return load_or_compute_corpus_stats(graphs, output=DEFAULT_COMPLEXITY_STATS_PATH)


def load_or_compute_quality_corpus_stats(
    graphs: list[EventGraph],
    *,
    output: Path = DEFAULT_QUALITY_STATS_PATH,
    complexity_output: Path = DEFAULT_COMPLEXITY_STATS_PATH,
) -> QualityCorpusStats:
    if output.exists():
        try:
            loaded = QualityCorpusStats.model_validate(json.loads(output.read_text(encoding="utf-8")))
            if loaded.graph_count == len(graphs):
                return loaded
        except (json.JSONDecodeError, ValueError):
            pass

    complexity_stats = load_or_compute_corpus_stats(graphs, output=complexity_output)
    stats = compute_quality_corpus_stats(graphs, complexity_stats=complexity_stats)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(stats.model_dump(mode="json"), indent=2), encoding="utf-8")
    return stats


def evaluate_generation(
    generated_graph: EventGraph,
    corpus_stats: QualityCorpusStats,
    *,
    reference_graph: EventGraph | None = None,
) -> QualityReport:
    snapshot = _quality_snapshot(generated_graph)
    complexity_profile = compute_complexity(generated_graph)
    complexity_comparison = compare_profile_to_corpus(complexity_profile, corpus_stats.complexity)

    metrics: dict[str, float] = {
        "chord_kl_divergence": round(
            _kl_divergence(snapshot["chord_distribution"], corpus_stats.chord_distribution),
            4,
        ),
        "cadence_kl_divergence": round(
            _kl_divergence(snapshot["cadence_distribution"], corpus_stats.cadence_distribution),
            4,
        ),
        "chord_variety_z": _z_score(snapshot["chord_variety"], corpus_stats.metric_summaries.get("chord_variety")),
        "harmonic_rhythm_mean_z": _z_score(
            snapshot["harmonic_rhythm_mean"],
            corpus_stats.metric_summaries.get("harmonic_rhythm_mean"),
        ),
        "nonharmonic_tone_density_z": _z_score(
            snapshot["nonharmonic_tone_density"],
            corpus_stats.metric_summaries.get("nonharmonic_tone_density"),
        ),
        "contrary_motion_ratio_z": _z_score(
            snapshot["contrary_motion_ratio"],
            corpus_stats.metric_summaries.get("contrary_motion_ratio"),
        ),
        "parallel_violation_rate_z": _z_score(
            snapshot["parallel_violation_rate"],
            corpus_stats.metric_summaries.get("parallel_violation_rate"),
        ),
        "parallel_violation_rate": round(snapshot["parallel_violation_rate"], 4),
        "validation_pass_rate": 1.0 if snapshot["passed_validation"] else 0.0,
    }

    for field, z_score in complexity_comparison.z_scores.items():
        metrics[f"{field}_z"] = round(z_score, 4)
    metrics["complexity_divergence_to_corpus"] = round(complexity_comparison.divergence, 4)

    if reference_graph is not None:
        reference_profile = compute_complexity(reference_graph)
        metrics["harmonic_similarity_to_reference"] = round(
            harmonic_similarity(generated_graph, reference_graph),
            4,
        )
        metrics["complexity_divergence_to_reference"] = round(
            complexity_divergence(complexity_profile, reference_profile, corpus_stats=corpus_stats.complexity),
            4,
        )

    fidelity_components = [
        _inverse_penalty(metrics["chord_kl_divergence"]),
        _inverse_penalty(metrics["cadence_kl_divergence"]),
        _z_component(metrics["chord_variety_z"]),
        _z_component(metrics["harmonic_rhythm_mean_z"]),
        _z_component(metrics["nonharmonic_tone_density_z"]),
        _z_component(metrics["contrary_motion_ratio_z"]),
        _z_component(metrics["parallel_violation_rate_z"]),
        _z_component(metrics["harmonic_entropy_z"]),
        _z_component(metrics["melodic_information_content_z"]),
        _z_component(metrics["voice_leading_mutual_information_z"]),
        _z_component(metrics["pitch_lz_complexity_z"]),
        _z_component(metrics["rhythm_lz_complexity_z"]),
        _z_component(metrics["average_tonal_tension_z"]),
        _z_component(metrics["peak_tonal_tension_z"]),
        max(0.0, 1.0 - min(metrics["parallel_violation_rate"] * 8.0, 1.0)),
        metrics["validation_pass_rate"],
    ]
    if "harmonic_similarity_to_reference" in metrics:
        fidelity_components.append(metrics["harmonic_similarity_to_reference"])
    if "complexity_divergence_to_reference" in metrics:
        fidelity_components.append(_inverse_penalty(metrics["complexity_divergence_to_reference"]))

    fidelity = round(_mean(fidelity_components) * 100.0, 2)
    return QualityReport(
        work_id=generated_graph.work_id,
        bach_fidelity_score=fidelity,
        metrics=metrics,
        passed_validation=snapshot["passed_validation"],
    )


def _quality_snapshot(graph: EventGraph) -> dict[str, object]:
    harmony = summarize_harmony(graph)
    cadences = detect_cadences(graph)
    rhythm = extract_harmonic_rhythm(graph)
    texture = analyze_chorale_texture(graph)
    validation = validate_graph(graph)

    chord_counts = Counter(
        event.roman_numeral_candidate_set[0]
        for event in harmony
        if event.roman_numeral_candidate_set
    )
    cadence_counts = Counter(cadence.cadence_type for cadence in cadences if cadence.cadence_type)
    nonharmonic_count = sum(len(event.nonharmonic_tone_tags) for event in harmony)

    motion_total = sum(
        float(texture.get(key, 0))
        for key in ("contrary", "similar", "oblique", "parallel")
    )
    parallel_count = (
        float(texture.get("counterpoint", {}).get("parallel_5ths", 0))
        + float(texture.get("counterpoint", {}).get("parallel_8ves", 0))
    )
    note_count = len([note for note in graph.notes if note.midi is not None and not note.is_rest])

    return {
        "chord_counts": chord_counts,
        "chord_distribution": _normalize_counter(chord_counts),
        "cadence_counts": cadence_counts,
        "cadence_distribution": _normalize_counter(cadence_counts),
        "chord_variety": float(len(chord_counts)),
        "harmonic_rhythm_mean": float(rhythm.mean_changes_per_measure),
        "nonharmonic_tone_density": _safe_div(nonharmonic_count, len(harmony)),
        "contrary_motion_ratio": _safe_div(float(texture.get("contrary", 0)), motion_total),
        "parallel_violation_rate": _safe_div(parallel_count, max(note_count / 4.0, 1.0)),
        "passed_validation": validation.passed,
    }


def _normalize_counter(counter: Counter[str]) -> dict[str, float]:
    total = float(sum(counter.values()))
    if total == 0:
        return {}
    return {
        key: round(value / total, 8)
        for key, value in sorted(counter.items())
    }


def _kl_divergence(left: dict[str, float], right: dict[str, float], *, epsilon: float = 1e-9) -> float:
    support = sorted(set(left) | set(right))
    if not support:
        return 0.0

    left_total = sum(left.get(key, 0.0) + epsilon for key in support)
    right_total = sum(right.get(key, 0.0) + epsilon for key in support)
    divergence = 0.0
    for key in support:
        p = (left.get(key, 0.0) + epsilon) / left_total
        q = (right.get(key, 0.0) + epsilon) / right_total
        divergence += p * math.log2(p / q)
    return max(0.0, divergence)


def _z_score(value: float, summary: MetricSummary | None) -> float:
    if summary is None or summary.std == 0:
        return 0.0
    return round((float(value) - summary.mean) / summary.std, 4)


def _z_component(z_score: float) -> float:
    return max(0.0, 1.0 - min(abs(z_score) / 3.0, 1.0))


def _inverse_penalty(value: float) -> float:
    return 1.0 / (1.0 + max(value, 0.0))


def _safe_div(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


__all__ = [
    "DEFAULT_QUALITY_STATS_PATH",
    "QualityCorpusStats",
    "QualityReport",
    "compute_quality_corpus_stats",
    "evaluate_generation",
    "load_or_compute_quality_corpus_stats",
]
