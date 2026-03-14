from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from bachbot.benchmark.complexity import (
    ComplexityCorpusStats,
    compare_profile_to_corpus,
    compute_complexity,
    compute_corpus_complexity_stats,
    complexity_divergence,
)
from bachbot.cli.main import app


def test_compute_complexity_returns_profile(simple_chorale_graph) -> None:
    profile = compute_complexity(simple_chorale_graph)

    assert profile.work_id == "BWV-TEST"
    assert profile.harmonic_entropy >= 0.0
    assert profile.melodic_information_content >= 0.0
    assert profile.voice_leading_mutual_information >= 0.0
    assert profile.pitch_lz_complexity > 0.0
    assert profile.rhythm_lz_complexity > 0.0
    assert profile.average_tonal_tension >= 0.0
    assert profile.peak_tonal_tension >= profile.average_tonal_tension
    assert profile.tonal_tension_curve


def test_compute_corpus_complexity_stats(simple_chorale_graph) -> None:
    stats = compute_corpus_complexity_stats([simple_chorale_graph, simple_chorale_graph])

    assert isinstance(stats, ComplexityCorpusStats)
    assert stats.graph_count == 2
    assert "harmonic_entropy" in stats.metrics
    assert stats.metrics["harmonic_entropy"].mean >= 0.0


def test_complexity_comparison_and_divergence(simple_chorale_graph) -> None:
    profile = compute_complexity(simple_chorale_graph)
    stats = compute_corpus_complexity_stats([simple_chorale_graph, simple_chorale_graph])

    comparison = compare_profile_to_corpus(profile, stats)
    divergence = complexity_divergence(profile, profile, corpus_stats=stats)

    assert set(comparison.z_scores)
    assert divergence == 0.0


def test_complexity_cli_writes_json(tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "complexity.json"

    result = runner.invoke(
        app,
        [
            "benchmark",
            "complexity",
            "--sample",
            "5",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["graph_count"] == 5
    assert "harmonic_entropy" in payload["metrics"]
