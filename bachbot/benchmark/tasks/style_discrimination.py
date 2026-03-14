"""Task 4: Given two chorales (one Bach, one generated), identify which is authentic."""

from __future__ import annotations

import hashlib

from bachbot.benchmark.metrics import pitch_class_entropy, stepwise_fraction
from bachbot.benchmark.protocol import (
    BenchTask,
    TaskInput,
    TaskOutput,
    TaskResult,
    extract_voice_notes,
)
from bachbot.encodings.event_graph import EventGraph


class StyleDiscriminationTask(BenchTask):
    task_type = "style_discrimination"

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

            # Generate a Bachbot harmonization of the same soprano
            from bachbot.composition.service import compose_chorale_study

            soprano = extract_voice_notes(graph, "soprano")
            if not soprano:
                continue

            try:
                gen_graph, _, _ = compose_chorale_study(graph, bundle=bundle)
            except Exception:
                continue

            # Deterministic randomization: hash decides order (Bach=0 or Bach=1)
            order_seed = int(hashlib.sha256(wid.encode()).hexdigest()[:8], 16) % 2

            if order_seed == 0:
                pair = [
                    [n.model_dump() for n in graph.notes],
                    [n.model_dump() for n in gen_graph.notes],
                ]
                bach_index = 0
            else:
                pair = [
                    [n.model_dump() for n in gen_graph.notes],
                    [n.model_dump() for n in graph.notes],
                ]
                bach_index = 1

            inp = TaskInput(
                task_id=f"style_discrimination:{wid}",
                task_type=self.task_type,
                metadata={
                    "work_id": wid,
                    "bach_index": bach_index,
                },
                extra={
                    "chorale_a_notes": pair[0],
                    "chorale_b_notes": pair[1],
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
        bach_index = task_input.metadata.get("bach_index", 0)
        predicted = task_output.output_labels
        correct = 1.0 if predicted and predicted[0] == str(bach_index) else 0.0

        confidence = task_output.confidence
        calibration = abs(confidence - correct)

        return TaskResult(
            task_id=task_input.task_id,
            task_type=self.task_type,
            chorale_id=task_input.metadata.get("work_id", ""),
            metrics={
                "discrimination_accuracy": correct,
                "confidence_calibration": round(1.0 - calibration, 4),
                "composite": correct,
            },
            passed=correct > 0.5,
        )

    def run_baseline(
        self,
        task_input: TaskInput,
        bundle: dict | None = None,
    ) -> TaskOutput:
        """Heuristic discriminator: higher entropy + more stepwise = likely Bach."""
        from bachbot.models.base import TypedNote

        notes_a = [TypedNote.model_validate(d) for d in task_input.extra.get("chorale_a_notes", [])]
        notes_b = [TypedNote.model_validate(d) for d in task_input.extra.get("chorale_b_notes", [])]

        score_a = _style_score(notes_a)
        score_b = _style_score(notes_b)

        predicted_index = "0" if score_a >= score_b else "1"
        confidence = abs(score_a - score_b) / max(score_a + score_b, 0.01)

        return TaskOutput(
            task_id=task_input.task_id,
            output_labels=[predicted_index],
            confidence=min(1.0, 0.5 + confidence),
        )


def _style_score(notes: list) -> float:
    """Simple style heuristic: entropy + chord variety + stepwise motion."""
    from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
    from bachbot.models.section import Section

    if not notes:
        return 0.0

    graph = EventGraph(
        metadata=EncodingMetadata(encoding_id="tmp", source_format="benchmark"),
        section=Section(
            section_id="s1", work_id="tmp", label="tmp",
            section_type="tmp", measure_start=1, measure_end=1,
        ),
        notes=notes,
    )

    entropy = pitch_class_entropy(graph)
    sw = stepwise_fraction(graph, "soprano")
    unique_pitches = len({n.midi for n in notes if n.midi is not None})
    return entropy + sw + unique_pitches * 0.01
