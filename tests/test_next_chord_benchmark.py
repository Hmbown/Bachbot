from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bachbot.benchmark.next_chord_eval import run_next_chord_benchmark
from bachbot.benchmark.split import compute_grouped_split
from bachbot.cli.main import app
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice

_CORPUS_NORM = Path("data/normalized/dcml_bach_chorales")
_CORPUS_DERIVED = Path("data/derived/dcml_bach_chorales")


def _has_corpus() -> bool:
    return _CORPUS_NORM.exists() and _CORPUS_DERIVED.exists()


def _voice(voice_id: str) -> Voice:
    return Voice(
        voice_id=voice_id,
        section_id="s1",
        part_name=voice_id,
        normalized_voice_name=voice_id,
        instrument_or_role=voice_id,
    )


def _note(voice_id: str, midi: int, onset: float, measure: int) -> TypedNote:
    return TypedNote(
        pitch=f"midi-{midi}",
        midi=midi,
        duration_quarters=1.0,
        offset_quarters=onset,
        measure_number=measure,
        beat=1.0 + (onset % 4.0),
        voice_id=voice_id,
        part_name=voice_id,
        source_ref=f"s1:m{measure}",
    )


def _graph(work_id: str, soprano_line: list[int]) -> EventGraph:
    notes = [_note("S", midi, float(idx), idx + 1) for idx, midi in enumerate(soprano_line)]
    notes.extend(_note("B", 48, float(idx), idx + 1) for idx in range(len(soprano_line)))
    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id=work_id,
            work_id=work_id,
            source_format="test",
            key_estimate=KeyEstimate(tonic="C", mode="major", confidence=0.9),
        ),
        section=Section(
            section_id="s1",
            work_id=work_id,
            label=work_id,
            section_type="chorale",
            measure_start=1,
            measure_end=len(soprano_line),
        ),
        voices=[_voice("S"), _voice("B")],
        notes=notes,
    )


def test_compute_grouped_split_keeps_duplicate_melodies_together() -> None:
    graphs = [
        _graph("notes__001 Alpha", [60, 62, 64, 65]),
        _graph("notes__002 Beta", [60, 62, 64, 65]),
        _graph("notes__003 Gamma", [67, 69, 71, 72]),
        _graph("notes__004 Delta", [65, 64, 62, 60]),
    ]

    split = compute_grouped_split(graphs)

    assert split["notes__001 Alpha"] == split["notes__002 Beta"]
    assert set(split.values()) <= {"train", "val", "test"}


@pytest.mark.skipif(not _has_corpus(), reason="No corpus data available")
def test_run_next_chord_benchmark_reports_all_baselines() -> None:
    payload = run_next_chord_benchmark(sample=30)

    assert payload["split"] == "test"
    assert payload["train_instance_count"] > 0
    assert payload["eval_instance_count"] > 0
    assert set(payload["results"]) == {"unigram", "bigram", "degree_chord_map"}
    for metrics in payload["results"].values():
        assert metrics["top1_accuracy"] >= 0.0
        assert metrics["top3_accuracy"] >= metrics["top1_accuracy"]
        assert metrics["perplexity"] > 0.0


@pytest.mark.skipif(not _has_corpus(), reason="No corpus data available")
def test_predict_next_cli_writes_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(repo_root)
    output = tmp_path / "next-chord.json"

    result = runner.invoke(
        app,
        [
            "benchmark",
            "predict-next",
            "--all-models",
            "--sample",
            "30",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "NEXT-CHORD BENCHMARK" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert set(payload["results"]) == {"unigram", "bigram", "degree_chord_map"}


@pytest.mark.skipif(not _has_corpus(), reason="No corpus data available")
def test_benchmark_run_accepts_task_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(repo_root)
    output = tmp_path / "suite.json"

    result = runner.invoke(
        app,
        [
            "benchmark",
            "run",
            "--task",
            "next-chord",
            "--sample",
            "20",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    suite = json.loads(output.read_text(encoding="utf-8"))
    assert "next_chord" in suite["task_summaries"]
