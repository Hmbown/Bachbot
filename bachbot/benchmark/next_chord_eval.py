"""Dedicated evaluation helpers for the next-chord benchmark."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bachbot.benchmark.runner import _load_corpus
from bachbot.benchmark.split import compute_grouped_split, load_split_manifest, save_split_manifest
from bachbot.benchmark.tasks.next_chord import NextChordTask, _function
from bachbot.composition.generators.pattern_fill import (
    DEFAULT_DEGREE_CHORD_MAJOR,
    DEFAULT_DEGREE_CHORD_MINOR,
)

_SPLIT_PATH = Path("data/manifests/bachbench_split_v2.json")
_EPSILON = 1e-12


@dataclass(frozen=True)
class PredictionInstance:
    work_id: str
    context_chords: tuple[str, ...]
    target_chord: str
    key_tonic: str
    key_mode: str
    target_soprano_degree: str | None = None


def load_or_compute_split(graphs) -> dict[str, str]:
    current_ids = {graph.work_id for graph in graphs}
    if _SPLIT_PATH.exists():
        split = load_split_manifest(_SPLIT_PATH)
        if split and set(split.values()) >= {"train", "val", "test"} and current_ids <= set(split):
            return split
    split = compute_grouped_split(graphs)
    save_split_manifest(split, _SPLIT_PATH)
    return split


def build_prediction_instances(
    graphs,
    bundles,
    split_map: dict[str, str],
    split_name: str,
) -> list[PredictionInstance]:
    task = NextChordTask()
    split_ids = {work_id for work_id, bucket in split_map.items() if bucket == split_name}
    raw_instances = task.generate_instances(graphs, bundles, split_ids)
    instances: list[PredictionInstance] = []
    for task_input, _, _ in raw_instances:
        instances.append(
            PredictionInstance(
                work_id=str(task_input.metadata.get("work_id", "")),
                context_chords=tuple(task_input.extra.get("context_chords", [])),
                target_chord=str(task_input.metadata.get("target_chord", "")),
                key_tonic=str(task_input.extra.get("key", "C")),
                key_mode=str(task_input.extra.get("mode", "major")),
                target_soprano_degree=task_input.extra.get("target_soprano_degree"),
            )
        )
    return instances


def summarize_split(split_map: dict[str, str]) -> dict[str, int]:
    counts = Counter(split_map.values())
    return {
        "train": counts.get("train", 0),
        "val": counts.get("val", 0),
        "test": counts.get("test", 0),
    }


def _rank_distribution(distribution: dict[str, float], top_k: int = 3) -> list[str]:
    return [
        label for label, _ in sorted(
            distribution.items(),
            key=lambda item: (-item[1], item[0]),
        )[:top_k]
    ]


class BaseNextChordPredictor:
    name = "base"

    def __init__(self) -> None:
        self.vocabulary: tuple[str, ...] = ("I",)

    def fit(self, instances: list[PredictionInstance]) -> None:
        vocab = sorted({instance.target_chord for instance in instances if instance.target_chord})
        self.vocabulary = tuple(vocab or ["I"])

    def distribution(self, instance: PredictionInstance) -> dict[str, float]:
        raise NotImplementedError


class UnigramPredictor(BaseNextChordPredictor):
    name = "unigram"

    def fit(self, instances: list[PredictionInstance]) -> None:
        super().fit(instances)
        self.counts = Counter(instance.target_chord for instance in instances if instance.target_chord)
        self.total = sum(self.counts.values())

    def distribution(self, instance: PredictionInstance) -> dict[str, float]:
        alpha = 1.0
        denom = self.total + alpha * len(self.vocabulary)
        return {
            label: (self.counts.get(label, 0) + alpha) / max(denom, 1.0)
            for label in self.vocabulary
        }


class BigramPredictor(BaseNextChordPredictor):
    name = "bigram"

    def fit(self, instances: list[PredictionInstance]) -> None:
        super().fit(instances)
        self.fallback = UnigramPredictor()
        self.fallback.fit(instances)
        self.followers: dict[str, Counter[str]] = defaultdict(Counter)
        for instance in instances:
            if not instance.context_chords or not instance.target_chord:
                continue
            self.followers[instance.context_chords[-1]][instance.target_chord] += 1

    def distribution(self, instance: PredictionInstance) -> dict[str, float]:
        if not instance.context_chords:
            return self.fallback.distribution(instance)
        last = instance.context_chords[-1]
        counts = self.followers.get(last)
        if not counts:
            return self.fallback.distribution(instance)
        alpha = 1.0
        denom = sum(counts.values()) + alpha * len(self.vocabulary)
        return {
            label: (counts.get(label, 0) + alpha) / max(denom, 1.0)
            for label in self.vocabulary
        }


class DegreeChordMapPredictor(BaseNextChordPredictor):
    name = "degree_chord_map"

    def fit(self, instances: list[PredictionInstance]) -> None:
        vocab = {instance.target_chord for instance in instances if instance.target_chord}
        vocab.update(DEFAULT_DEGREE_CHORD_MAJOR.values())
        vocab.update(DEFAULT_DEGREE_CHORD_MINOR.values())
        self.vocabulary = tuple(sorted(vocab or {"I"}))
        self.degree_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
        for instance in instances:
            if not instance.target_soprano_degree or not instance.target_chord:
                continue
            self.degree_counts[(instance.key_mode, instance.target_soprano_degree)][instance.target_chord] += 1

    def distribution(self, instance: PredictionInstance) -> dict[str, float]:
        defaults = DEFAULT_DEGREE_CHORD_MINOR if instance.key_mode == "minor" else DEFAULT_DEGREE_CHORD_MAJOR
        degree = instance.target_soprano_degree or "1"
        default_label = defaults.get(degree, "i" if instance.key_mode == "minor" else "I")
        counts = Counter(self.degree_counts.get((instance.key_mode, degree), {}))
        counts[default_label] += 1
        alpha = 0.5
        denom = sum(counts.values()) + alpha * len(self.vocabulary)
        return {
            label: (counts.get(label, 0) + alpha) / max(denom, 1.0)
            for label in self.vocabulary
        }


PREDICTORS = {
    "unigram": UnigramPredictor,
    "bigram": BigramPredictor,
    "degree_chord_map": DegreeChordMapPredictor,
}


def evaluate_predictor(
    predictor: BaseNextChordPredictor,
    train_instances: list[PredictionInstance],
    eval_instances: list[PredictionInstance],
) -> dict[str, float]:
    predictor.fit(train_instances)
    if not eval_instances:
        return {
            "instance_count": 0.0,
            "top1_accuracy": 0.0,
            "top3_accuracy": 0.0,
            "functional_accuracy": 0.0,
            "perplexity": 0.0,
        }

    top1_hits = 0
    top3_hits = 0
    function_hits = 0
    neg_log_likelihood = 0.0

    for instance in eval_instances:
        distribution = predictor.distribution(instance)
        ranked = _rank_distribution(distribution)
        top1_hits += int(bool(ranked) and ranked[0] == instance.target_chord)
        top3_hits += int(instance.target_chord in ranked[:3])
        function_hits += int(bool(ranked) and _function(ranked[0]) == _function(instance.target_chord))
        neg_log_likelihood += -math.log(max(distribution.get(instance.target_chord, 0.0), _EPSILON))

    total = float(len(eval_instances))
    return {
        "instance_count": total,
        "top1_accuracy": round(top1_hits / total, 4),
        "top3_accuracy": round(top3_hits / total, 4),
        "functional_accuracy": round(function_hits / total, 4),
        "perplexity": round(math.exp(neg_log_likelihood / total), 4),
    }


def run_next_chord_benchmark(
    *,
    model_names: list[str] | None = None,
    split: str = "test",
    sample: int | None = None,
    output: Path | None = None,
) -> dict[str, object]:
    graphs, bundles = _load_corpus()
    split_map = load_or_compute_split(graphs)
    train_instances = build_prediction_instances(graphs, bundles, split_map, "train")
    eval_instances = build_prediction_instances(graphs, bundles, split_map, split)
    if sample is not None:
        eval_instances = eval_instances[:sample]

    selected_models = model_names or list(PREDICTORS)
    results: dict[str, dict[str, float]] = {}
    for model_name in selected_models:
        predictor_cls = PREDICTORS[model_name]
        results[model_name] = evaluate_predictor(predictor_cls(), train_instances, eval_instances)

    payload: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "split": split,
        "split_summary": summarize_split(split_map),
        "train_instance_count": len(train_instances),
        "eval_instance_count": len(eval_instances),
        "results": results,
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload
