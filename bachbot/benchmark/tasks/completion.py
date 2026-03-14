"""Task 3: Given first half of chorale (all 4 voices), generate second half."""

from __future__ import annotations

from bachbot.benchmark.metrics import (
    harmonic_similarity,
    pitch_accuracy,
    validation_pass_rate,
    voice_leading_score,
)
from bachbot.benchmark.protocol import (
    BenchTask,
    TaskInput,
    TaskOutput,
    TaskResult,
    extract_voice_notes,
    truncate_graph,
)
from bachbot.encodings.event_graph import EventGraph


class CompletionTask(BenchTask):
    task_type = "completion"

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

            measures = graph.measure_numbers()
            if len(measures) < 4:
                continue
            midpoint = measures[len(measures) // 2]

            first_half = truncate_graph(graph, _measure_onset(graph, midpoint))
            if not first_half.notes:
                continue

            inp = TaskInput(
                task_id=f"completion:{wid}",
                task_type=self.task_type,
                input_notes=[n.model_dump() for n in first_half.notes],
                metadata={
                    "work_id": wid,
                    "midpoint_measure": midpoint,
                    "total_measures": len(measures),
                    "key": graph.metadata.key_estimate.tonic if graph.metadata.key_estimate else "",
                    "meter": graph.meter or "4/4",
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
        from bachbot.models.base import TypedNote

        midpoint = task_input.metadata.get("midpoint_measure", 1)
        gt_second_half = ground_truth.model_copy(update={
            "notes": [n for n in ground_truth.notes if n.measure_number >= midpoint],
        })

        pred_notes = [TypedNote.model_validate(d) for d in task_output.output_notes]
        pred_graph = ground_truth.model_copy(update={"notes": pred_notes})

        pa = pitch_accuracy(pred_graph, gt_second_half)
        hs = harmonic_similarity(pred_graph, gt_second_half)
        vl = voice_leading_score(pred_graph) if pred_notes else 0.0
        vp = validation_pass_rate(pred_graph) if pred_notes else 0.0

        # Length ratio (closer to 1.0 is better)
        gt_dur = gt_second_half.total_duration() if gt_second_half.notes else 1.0
        pred_dur = pred_graph.total_duration() if pred_notes else 0.0
        length_ratio = min(pred_dur / gt_dur, gt_dur / pred_dur) if gt_dur > 0 and pred_dur > 0 else 0.0

        composite = 0.3 * pa + 0.2 * hs + 0.2 * vl + 0.15 * vp + 0.15 * length_ratio

        return TaskResult(
            task_id=task_input.task_id,
            task_type=self.task_type,
            chorale_id=task_input.metadata.get("work_id", ""),
            metrics={
                "pitch_accuracy": round(pa, 4),
                "harmonic_similarity": round(hs, 4),
                "voice_leading_score": round(vl, 4),
                "validation_pass": round(vp, 4),
                "length_ratio": round(length_ratio, 4),
                "composite": round(composite, 4),
            },
            passed=composite >= 0.2,
        )

    def run_baseline(
        self,
        task_input: TaskInput,
        bundle: dict | None = None,
    ) -> TaskOutput:
        """Baseline: extract soprano from ground truth's second half and harmonize it.

        This is a 'cheating' upper-bound baseline — the soprano is given.
        """
        from bachbot.composition.service import compose_chorale_study
        from bachbot.models.base import TypedNote

        # We need the ground truth soprano for the second half.
        # Since we can't access it directly from task_input, return empty.
        # The runner will call this with the full graph available.
        return TaskOutput(task_id=task_input.task_id)


def _measure_onset(graph: EventGraph, measure: int) -> float:
    """Find the onset of the first note at or after the given measure."""
    for n in sorted(graph.notes, key=lambda n: n.offset_quarters):
        if n.measure_number >= measure:
            return n.offset_quarters
    return graph.global_end_offset()
