from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bachbot.benchmark.dashboard import (
    build_report_metadata,
    compare_benchmark_runs,
    load_snapshot,
    persist_benchmark_history,
)
from bachbot.cli import benchmark as benchmark_cli
from bachbot.cli.main import app


def _report(
    *,
    generated_at: str,
    git_commit: str,
    sample_size: int,
    evidence_pass_rate: float = 0.9,
    chord_variety: float = 10.0,
    parallel_violations: float = 0.5,
    voice_leading: float = 0.85,
    harmonic_similarity: float = 0.92,
) -> dict:
    return {
        "metadata": {
            "generated_at": generated_at,
            "git_commit": git_commit,
            "sample_size": sample_size,
            "split": "full",
            "source_output": "data/derived/benchmark_results.json",
        },
        "summary": {
            "sample_size": sample_size,
            "evidence_avg_pass_rate": evidence_pass_rate,
            "baseline_avg_pass_rate": 0.4,
            "evidence_avg_chord_variety": chord_variety,
            "baseline_avg_chord_variety": 6.0,
            "original_avg_chord_variety": 14.0,
            "evidence_avg_cadences": 4.0,
            "evidence_avg_parallel_violations": parallel_violations,
            "baseline_avg_parallel_violations": 3.0,
            "evidence_avg_voice_leading_score": voice_leading,
            "baseline_avg_voice_leading_score": 0.5,
            "evidence_avg_harmonic_similarity": harmonic_similarity,
            "baseline_avg_harmonic_similarity": 0.7,
            "evidence_avg_pitch_class_entropy": 3.2,
            "baseline_avg_pitch_class_entropy": 2.9,
            "original_avg_pitch_class_entropy": 3.4,
        },
        "results": [],
    }


def test_persist_benchmark_history_writes_latest_snapshot(tmp_path: Path) -> None:
    report = _report(
        generated_at="2026-03-09T12:00:00+00:00",
        git_commit="abc123def456",
        sample_size=12,
    )

    snapshot = persist_benchmark_history(report, history_dir=tmp_path)

    assert snapshot.exists()
    latest = tmp_path / "latest.json"
    assert latest.exists()
    payload = load_snapshot(snapshot)
    assert payload["metadata"]["git_commit"] == "abc123def456"
    assert payload["metadata"]["sample_size"] == 12
    assert payload["summary"]["evidence_avg_chord_variety"] == 10.0


def test_compare_benchmark_runs_flags_regressions() -> None:
    baseline = _report(
        generated_at="2026-03-09T12:00:00+00:00",
        git_commit="abc123def456",
        sample_size=12,
    )
    current = _report(
        generated_at="2026-03-10T12:00:00+00:00",
        git_commit="def456abc123",
        sample_size=12,
        evidence_pass_rate=0.8,
        chord_variety=8.0,
        parallel_violations=1.2,
        voice_leading=0.79,
        harmonic_similarity=0.85,
    )

    alerts = compare_benchmark_runs(current, baseline)

    metrics = {alert["metric"] for alert in alerts}
    assert "evidence_avg_pass_rate" in metrics
    assert "evidence_avg_chord_variety" in metrics
    assert "evidence_avg_parallel_violations" in metrics
    assert "evidence_avg_voice_leading_score" in metrics
    assert "evidence_avg_harmonic_similarity" in metrics


def test_benchmark_dashboard_cli_generates_html(tmp_path: Path) -> None:
    runner = CliRunner()
    persist_benchmark_history(
        _report(
            generated_at="2026-03-09T12:00:00+00:00",
            git_commit="abc123def456",
            sample_size=12,
        ),
        history_dir=tmp_path,
    )
    persist_benchmark_history(
        _report(
            generated_at="2026-03-10T12:00:00+00:00",
            git_commit="def456abc123",
            sample_size=16,
        ),
        history_dir=tmp_path,
    )
    output = tmp_path / "dashboard.html"

    result = runner.invoke(
        app,
        [
            "benchmark",
            "dashboard",
            "--history-dir",
            str(tmp_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    html = output.read_text(encoding="utf-8")
    assert "Bachbot Benchmark Dashboard" in html
    assert "chart-pass-rate" in html
    assert "chart-complexity" in html


def test_check_regressions_cli_fails_on_alert(tmp_path: Path) -> None:
    runner = CliRunner()
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(
        json.dumps(
            _report(
                generated_at="2026-03-09T12:00:00+00:00",
                git_commit="abc123def456",
                sample_size=12,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    current.write_text(
        json.dumps(
            _report(
                generated_at="2026-03-10T12:00:00+00:00",
                git_commit="def456abc123",
                sample_size=12,
                evidence_pass_rate=0.82,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "benchmark",
            "check-regressions",
            "--current",
            str(current),
            "--baseline",
            str(baseline),
        ],
    )

    assert result.exit_code == 1
    assert "Benchmark regression alerts:" in result.output


def test_benchmark_run_persists_history_and_dashboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = tmp_path / "data/raw/dcml_bach_chorales/notes/001.notes.tsv"
    bundle = tmp_path / "data/derived/dcml_bach_chorales/notes__001.evidence_bundle.json"
    history_dir = tmp_path / "data/derived/benchmarks"
    raw.parent.mkdir(parents=True, exist_ok=True)
    bundle.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("", encoding="utf-8")
    bundle.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_SHA", "feedfacecafe1234")

    def fake_glob(pattern: str) -> list[str]:
        if pattern.endswith("*.evidence_bundle.json"):
            return [str(bundle)]
        if pattern.endswith("*.notes.tsv"):
            return [str(raw)]
        return []

    fake_result = {
        "name": raw.name,
        "evidence": {
            "passed": True,
            "issues": {},
            "chords": {"I": 8},
            "variety": 12,
            "cadences": 4,
            "parallel_violations": 0,
            "voice_leading_score": 0.95,
            "harmonic_similarity": 0.94,
            "pitch_class_entropy": 3.5,
            "total_notes": 32,
        },
        "baseline": {
            "passed": False,
            "issues": {"parallel_8ves": 2},
            "chords": {"I": 8},
            "variety": 5,
            "parallel_violations": 3,
            "voice_leading_score": 0.4,
            "harmonic_similarity": 0.62,
            "pitch_class_entropy": 2.8,
            "total_notes": 32,
        },
        "original": {
            "chords": {"I": 8},
            "variety": 14,
            "pitch_class_entropy": 3.7,
        },
    }

    monkeypatch.setattr(benchmark_cli.glob, "glob", fake_glob)
    monkeypatch.setattr(benchmark_cli, "_evaluate_single", lambda raw_path, bundle_path, **kwargs: fake_result)

    benchmark_cli.run_benchmark(
        sample_size=1,
        output=tmp_path / "out.json",
        history_dir=history_dir,
        dashboard_output=history_dir / "index.html",
        suite="",
        task="",
        tasks="",
        split="test",
    )

    assert (history_dir / "latest.json").exists()
    assert (history_dir / "index.html").exists()
    payload = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["git_commit"] == "feedfacecafe"
    assert payload["summary"]["evidence_avg_parallel_violations"] == 0.0
