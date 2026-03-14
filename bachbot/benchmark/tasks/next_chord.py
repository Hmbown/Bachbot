"""Task 2: Next-chord prediction — given context, predict the next roman numeral."""

from __future__ import annotations

from bachbot.analysis.harmony.bass_patterns import degree_for_pitch_class
from bachbot.benchmark.protocol import (
    BenchTask,
    TaskInput,
    TaskOutput,
    TaskResult,
)
from bachbot.encodings.event_graph import EventGraph

# Functional classification
_TONIC = {"I", "i", "vi", "VI", "iii", "III"}
_SUBDOMINANT = {"ii", "II", "iv", "IV", "ii7", "IV7", "iiø7"}
_DOMINANT = {"V", "V7", "vii", "viio", "viio7", "viiø7"}


def _function(chord: str) -> str:
    base = chord.split("/")[0]
    if base in _TONIC:
        return "T"
    if base in _SUBDOMINANT:
        return "S"
    if base in _DOMINANT:
        return "D"
    return "O"


def _target_soprano_degree(graph: EventGraph, onset: float) -> str | None:
    key = graph.metadata.key_estimate
    if key is None:
        return None
    active = [
        note for note in graph.active_notes_at(onset)
        if not note.is_rest and note.midi is not None
    ]
    if not active:
        return None
    soprano = max(active, key=lambda note: note.midi or -1)
    if soprano.midi is None:
        return None
    return degree_for_pitch_class(soprano.midi % 12, key)


class NextChordTask(BenchTask):
    task_type = "next_chord"

    def generate_instances(
        self,
        graphs: list[EventGraph],
        bundles: list[dict],
        split_ids: set[str],
    ) -> list[tuple[TaskInput, EventGraph, dict]]:
        instances = []
        for graph, bundle in zip(graphs, bundles):
            wid = graph.work_id
            if wid not in split_ids:
                continue
            harmony = bundle.get("deterministic_findings", {}).get("harmony", [])
            chords = [
                (h.get("onset", i), h.get("roman_numeral_candidate_set", [""])[0])
                for i, h in enumerate(harmony)
                if h.get("roman_numeral_candidate_set")
            ]
            if len(chords) < 4:
                continue

            # Pick 3 prediction points: 25%, 50%, 75% through the chord sequence
            for frac in (0.25, 0.5, 0.75):
                idx = min(int(len(chords) * frac), len(chords) - 2)
                context = [c[1] for c in chords[:idx + 1]]
                target = chords[idx + 1][1]
                if not target:
                    continue

                inp = TaskInput(
                    task_id=f"next_chord:{wid}:{idx}",
                    task_type=self.task_type,
                    metadata={
                        "work_id": wid,
                        "prediction_index": idx,
                        "target_chord": target,
                    },
                    extra={
                        "context_chords": context,
                        "key": bundle.get("metadata", {}).get("key_tonic", "C"),
                        "mode": bundle.get("metadata", {}).get("key_mode", "major"),
                        "target_soprano_degree": _target_soprano_degree(graph, chords[idx + 1][0]),
                    },
                )
                instances.append((inp, graph, bundle))
        return instances

    def evaluate(
        self,
        task_input: TaskInput,
        task_output: TaskOutput,
        ground_truth: EventGraph,
        bundle: dict,
    ) -> TaskResult:
        target = task_input.metadata.get("target_chord", "")
        predictions = task_output.output_labels

        top1 = 1.0 if predictions and predictions[0] == target else 0.0
        top3 = 1.0 if target in predictions[:3] else 0.0
        func_match = 0.0
        if predictions:
            func_match = 1.0 if _function(predictions[0]) == _function(target) else 0.0

        composite = 0.5 * top1 + 0.25 * top3 + 0.25 * func_match

        return TaskResult(
            task_id=task_input.task_id,
            task_type=self.task_type,
            chorale_id=task_input.metadata.get("work_id", ""),
            metrics={
                "top1_accuracy": top1,
                "top3_accuracy": top3,
                "functional_accuracy": func_match,
                "composite": round(composite, 4),
            },
            passed=composite > 0.0,
        )

    def run_baseline(
        self,
        task_input: TaskInput,
        bundle: dict | None = None,
    ) -> TaskOutput:
        """Baseline: most common chord following the last context chord."""
        context = task_input.extra.get("context_chords", [])
        if not context:
            return TaskOutput(task_id=task_input.task_id, output_labels=["I"])

        # Simple bigram lookup from the bundle's full harmony
        if bundle:
            harmony = bundle.get("deterministic_findings", {}).get("harmony", [])
            chords = [
                h.get("roman_numeral_candidate_set", [""])[0]
                for h in harmony if h.get("roman_numeral_candidate_set")
            ]
            last = context[-1]
            followers: dict[str, int] = {}
            for a, b in zip(chords, chords[1:]):
                if a == last and b:
                    followers[b] = followers.get(b, 0) + 1
            if followers:
                ranked = sorted(followers, key=followers.get, reverse=True)
                return TaskOutput(
                    task_id=task_input.task_id,
                    output_labels=ranked[:3],
                )

        # Fallback: predict V after everything
        return TaskOutput(task_id=task_input.task_id, output_labels=["V", "I", "IV"])
