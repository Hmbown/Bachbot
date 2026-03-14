from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from bachbot.benchmark.complexity import ComplexityCorpusStats
from bachbot.benchmark.quality import (
    QualityCorpusStats,
    evaluate_generation,
    load_or_compute_quality_corpus_stats,
)
from bachbot.cli.main import app


def test_evaluate_generation_returns_quality_report(tmp_path: Path, simple_chorale_graph) -> None:
    stats = load_or_compute_quality_corpus_stats(
        [simple_chorale_graph],
        output=tmp_path / "quality_stats.json",
        complexity_output=tmp_path / "complexity_stats.json",
    )

    report = evaluate_generation(
        simple_chorale_graph,
        stats,
        reference_graph=simple_chorale_graph,
    )

    assert 0.0 <= report.bach_fidelity_score <= 100.0
    assert report.passed_validation is True
    assert len(report.metrics) >= 10
    assert "chord_kl_divergence" in report.metrics
    assert "harmonic_entropy_z" in report.metrics
    assert "harmonic_similarity_to_reference" in report.metrics


def test_quality_stats_roundtrip(tmp_path: Path, simple_chorale_graph) -> None:
    stats_path = tmp_path / "quality_stats.json"
    complexity_path = tmp_path / "complexity_stats.json"

    first = load_or_compute_quality_corpus_stats(
        [simple_chorale_graph],
        output=stats_path,
        complexity_output=complexity_path,
    )
    second = load_or_compute_quality_corpus_stats(
        [simple_chorale_graph],
        output=stats_path,
        complexity_output=complexity_path,
    )

    assert first.graph_count == 1
    assert second.graph_count == 1
    assert abs(sum(first.chord_distribution.values()) - 1.0) < 1e-6
    assert set(first.metric_summaries) == {
        "chord_variety",
        "harmonic_rhythm_mean",
        "nonharmonic_tone_density",
        "contrary_motion_ratio",
        "parallel_violation_rate",
    }


def test_benchmark_quality_command_writes_report(
    tmp_path: Path,
    monkeypatch,
    simple_chorale_graph,
) -> None:
    runner = CliRunner()
    raw = tmp_path / "data/raw/dcml_bach_chorales/notes/001.notes.tsv"
    bundle = tmp_path / "data/derived/dcml_bach_chorales/notes__001.evidence_bundle.json"
    output = tmp_path / "quality.json"
    stats_output = tmp_path / "quality_stats.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    bundle.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("", encoding="utf-8")
    bundle.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def fake_glob(pattern: str) -> list[str]:
        if pattern.endswith("*.evidence_bundle.json"):
            return [str(bundle)]
        if pattern.endswith("*.notes.tsv"):
            return [str(raw)]
        return []

    fake_stats = QualityCorpusStats(
        graph_count=1,
        complexity=ComplexityCorpusStats(graph_count=1, metrics={}),
        chord_distribution={"I": 1.0},
        cadence_distribution={"PAC": 1.0},
        metric_summaries={},
    )
    fake_result = {
        "name": raw.name,
        "evidence": {
            "work_id": "evidence",
            "bach_fidelity_score": 82.5,
            "metrics": {
                "chord_kl_divergence": 0.12,
                "cadence_kl_divergence": 0.08,
                "harmonic_similarity_to_reference": 0.91,
            },
            "passed_validation": True,
        },
        "baseline": {
            "work_id": "baseline",
            "bach_fidelity_score": 61.4,
            "metrics": {
                "chord_kl_divergence": 0.31,
                "cadence_kl_divergence": 0.22,
                "harmonic_similarity_to_reference": 0.73,
            },
            "passed_validation": False,
        },
    }

    from bachbot.cli import benchmark as benchmark_cli

    monkeypatch.setattr(benchmark_cli.glob, "glob", fake_glob)
    monkeypatch.setattr(benchmark_cli, "_load_corpus", lambda limit=None: ([simple_chorale_graph], [{}]))
    monkeypatch.setattr(benchmark_cli, "load_or_compute_quality_corpus_stats", lambda graphs, output: fake_stats)
    monkeypatch.setattr(benchmark_cli, "_evaluate_quality_single", lambda raw_path, bundle_path, quality_stats: fake_result)

    result = runner.invoke(
        app,
        [
            "benchmark",
            "quality",
            "--sample",
            "1",
            "--output",
            str(output),
            "--corpus-stats-output",
            str(stats_output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "QUALITY BENCHMARK" in result.output
    assert "QUALITY COMPARISON TABLE" in result.output
    assert "Chorale" in result.output
    assert "Ev score" in result.output
    row_line = next(
        line for line in result.output.splitlines()
        if "001.notes.tsv" in line and "82.50" in line
    )
    assert "61.40" in row_line
    assert "0.1200" in row_line
    assert "0.3100" in row_line
    assert "0.0800" in row_line
    assert "0.2200" in row_line
    assert row_line.rstrip().endswith("evidence")

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["evidence_avg_bach_fidelity"] == 82.5
    assert payload["summary"]["baseline_avg_bach_fidelity"] == 61.4
    assert payload["summary"]["evidence_beats_baseline_on_chord_kl"] is True
