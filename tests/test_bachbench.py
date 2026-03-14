"""Tests for BachBench benchmark suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bachbot.benchmark.leaderboard import format_leaderboard, print_leaderboard
from bachbot.benchmark.metrics import (
    cadence_f1,
    cosine_sim,
    harmonic_similarity,
    pitch_accuracy,
    pitch_class_entropy,
    voice_leading_score,
)
from bachbot.benchmark.protocol import (
    SuiteResult,
    TaskInput,
    TaskOutput,
    TaskResult,
    extract_voice_notes,
    truncate_graph,
)
from bachbot.benchmark.split import compute_split
from bachbot.benchmark.tasks import TASK_REGISTRY

_CORPUS_NORM = Path("data/normalized/dcml_bach_chorales")
_CORPUS_DERIVED = Path("data/derived/dcml_bach_chorales")


def _first_corpus_pair() -> tuple[Path, Path] | None:
    for gp in sorted(_CORPUS_NORM.glob("*.event_graph.json"))[:1]:
        stem = gp.name.replace(".event_graph.json", "")
        bp = _CORPUS_DERIVED / f"{stem}.evidence_bundle.json"
        if bp.exists():
            return gp, bp
    return None


# ── Split tests ───────────────────────────────────────────────────────

def test_split_deterministic() -> None:
    ids = [f"BWV-{i:03d}" for i in range(100)]
    s1 = compute_split(ids)
    s2 = compute_split(ids)
    assert s1 == s2


def test_split_stable_on_addition() -> None:
    ids = [f"BWV-{i:03d}" for i in range(50)]
    s1 = compute_split(ids)
    ids_extended = ids + [f"BWV-{i:03d}" for i in range(50, 100)]
    s2 = compute_split(ids_extended)
    for eid in ids:
        assert s1[eid] == s2[eid], f"Split changed for {eid} after adding new IDs"


def test_split_roughly_balanced() -> None:
    ids = [f"BWV-{i:03d}" for i in range(1000)]
    s = compute_split(ids)
    test_count = sum(1 for v in s.values() if v == "test")
    assert 150 < test_count < 250, f"Expected ~200 test, got {test_count}"


# ── Metric tests ──────────────────────────────────────────────────────

def test_cosine_sim_identical() -> None:
    assert cosine_sim([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_cosine_sim_orthogonal() -> None:
    assert cosine_sim([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)


def test_cadence_f1_perfect() -> None:
    assert cadence_f1([1, 5, 10], [1, 5, 10]) == pytest.approx(1.0)


def test_cadence_f1_no_overlap() -> None:
    assert cadence_f1([1, 2], [3, 4]) == pytest.approx(0.0)


def test_pitch_accuracy_identical_graph(simple_chorale_graph) -> None:
    assert pitch_accuracy(simple_chorale_graph, simple_chorale_graph) == pytest.approx(1.0)


def test_voice_leading_score_valid(simple_chorale_graph) -> None:
    score = voice_leading_score(simple_chorale_graph)
    assert 0.0 <= score <= 1.0


def test_harmonic_similarity_identical(simple_chorale_graph) -> None:
    assert harmonic_similarity(simple_chorale_graph, simple_chorale_graph) == pytest.approx(1.0)


def test_pitch_class_entropy_positive(simple_chorale_graph) -> None:
    assert pitch_class_entropy(simple_chorale_graph) > 0


# ── Protocol tests ────────────────────────────────────────────────────

def test_task_input_roundtrip() -> None:
    inp = TaskInput(task_id="test:1", task_type="harmonization", metadata={"key": "C"})
    data = inp.model_dump()
    restored = TaskInput.model_validate(data)
    assert restored.task_id == "test:1"


def test_suite_result_roundtrip() -> None:
    suite = SuiteResult(
        timestamp="2026-01-01",
        solver_name="test",
        task_summaries={"harmonization": {"composite": 0.5}},
    )
    data = suite.model_dump()
    restored = SuiteResult.model_validate(data)
    assert restored.solver_name == "test"


def test_extract_voice_notes(simple_chorale_graph) -> None:
    soprano = extract_voice_notes(simple_chorale_graph, "soprano")
    assert len(soprano) > 0
    assert all(n.midi is not None for n in soprano)


def test_truncate_graph(simple_chorale_graph) -> None:
    onsets = sorted({n.offset_quarters for n in simple_chorale_graph.notes})
    mid = onsets[len(onsets) // 2]
    truncated = truncate_graph(simple_chorale_graph, mid)
    assert len(truncated.notes) < len(simple_chorale_graph.notes)
    assert all(n.offset_quarters < mid for n in truncated.notes)


# ── Task registry tests ──────────────────────────────────────────────

def test_task_registry_has_4_tasks() -> None:
    assert len(TASK_REGISTRY) == 4
    assert "harmonization" in TASK_REGISTRY
    assert "next_chord" in TASK_REGISTRY
    assert "completion" in TASK_REGISTRY
    assert "style_discrimination" in TASK_REGISTRY


# ── Leaderboard tests ────────────────────────────────────────────────

def test_leaderboard_format() -> None:
    suite = SuiteResult(
        timestamp="2026-01-01",
        solver_name="test",
        split="test",
        corpus_size=72,
        task_summaries={
            "harmonization": {"composite": 0.65, "pitch_accuracy_atb": 0.3},
        },
    )
    lb = format_leaderboard(suite)
    assert lb["schema_version"] == "1.0.0"
    assert lb["composite_score"] == 0.65
    assert "harmonization" in lb["scores"]


def test_leaderboard_print() -> None:
    suite = SuiteResult(
        timestamp="2026-01-01",
        solver_name="test",
        task_summaries={"harmonization": {"composite": 0.5}},
    )
    text = print_leaderboard(suite)
    assert "test" in text
    assert "harmonization" in text


# ── Corpus integration tests ─────────────────────────────────────────

@pytest.mark.skipif(not _first_corpus_pair(), reason="No corpus data available")
def test_harmonization_generate_and_evaluate() -> None:
    """Integration: harmonization task generates instances and evaluates baseline."""
    from bachbot.encodings.event_graph import EventGraph

    gp, bp = _first_corpus_pair()
    graph = EventGraph.model_validate(json.loads(gp.read_text(encoding="utf-8")))
    bundle = json.loads(bp.read_text(encoding="utf-8"))

    task = TASK_REGISTRY["harmonization"]
    instances = task.generate_instances([graph], [bundle], {graph.work_id})
    assert len(instances) == 1

    inp, gt, bun = instances[0]
    assert inp.task_type == "harmonization"
    assert len(inp.input_notes) > 0

    output = task.run_baseline(inp, bundle=bun)
    result = task.evaluate(inp, output, gt, bun)
    assert result.task_type == "harmonization"
    assert "composite" in result.metrics


@pytest.mark.skipif(not _first_corpus_pair(), reason="No corpus data available")
def test_next_chord_generate_and_evaluate() -> None:
    """Integration: next_chord task generates instances and evaluates baseline."""
    from bachbot.encodings.event_graph import EventGraph

    gp, bp = _first_corpus_pair()
    graph = EventGraph.model_validate(json.loads(gp.read_text(encoding="utf-8")))
    bundle = json.loads(bp.read_text(encoding="utf-8"))

    task = TASK_REGISTRY["next_chord"]
    instances = task.generate_instances([graph], [bundle], {graph.work_id})
    assert len(instances) >= 1

    inp, gt, bun = instances[0]
    output = task.run_baseline(inp, bundle=bun)
    result = task.evaluate(inp, output, gt, bun)
    assert result.task_type == "next_chord"
    assert "top1_accuracy" in result.metrics
