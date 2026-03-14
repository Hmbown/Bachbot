"""Task 1: Given soprano melody, generate SATB harmonization."""

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
)
from bachbot.encodings.event_graph import EventGraph


class HarmonizationTask(BenchTask):
    task_type = "harmonization"

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
            soprano = extract_voice_notes(graph, "soprano")
            if not soprano:
                continue
            inp = TaskInput(
                task_id=f"harmonization:{wid}",
                task_type=self.task_type,
                input_notes=[n.model_dump() for n in soprano],
                metadata={
                    "work_id": wid,
                    "key": graph.metadata.key_estimate.tonic if graph.metadata.key_estimate else "",
                    "meter": graph.meter or "4/4",
                    "measure_count": len(graph.measure_numbers()),
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

        pred_notes = [TypedNote.model_validate(d) for d in task_output.output_notes]
        pred_graph = ground_truth.model_copy(update={"notes": pred_notes})

        pa = pitch_accuracy(pred_graph, ground_truth, voices=["alto", "tenor", "bass"])
        vl = voice_leading_score(pred_graph)
        hs = harmonic_similarity(pred_graph, ground_truth)
        vp = validation_pass_rate(pred_graph)

        composite = 0.4 * pa + 0.2 * vl + 0.2 * hs + 0.2 * vp

        return TaskResult(
            task_id=task_input.task_id,
            task_type=self.task_type,
            chorale_id=task_input.metadata.get("work_id", ""),
            metrics={
                "pitch_accuracy_atb": round(pa, 4),
                "voice_leading_score": round(vl, 4),
                "harmonic_similarity": round(hs, 4),
                "validation_pass": round(vp, 4),
                "composite": round(composite, 4),
            },
            passed=vp >= 0.5 and composite >= 0.3,
        )

    def run_baseline(
        self,
        task_input: TaskInput,
        bundle: dict | None = None,
    ) -> TaskOutput:
        from bachbot.composition.service import compose_chorale_study
        from bachbot.encodings.event_graph import EventGraph as EG
        from bachbot.models.base import TypedNote

        soprano_notes = [TypedNote.model_validate(d) for d in task_input.input_notes]
        if not soprano_notes:
            return TaskOutput(task_id=task_input.task_id)

        # Build minimal cantus graph from soprano notes
        cantus = _build_cantus_graph(soprano_notes, task_input.metadata)

        try:
            result_graph, _, _ = compose_chorale_study(cantus, bundle=bundle)
            return TaskOutput(
                task_id=task_input.task_id,
                output_notes=[n.model_dump() for n in result_graph.notes],
            )
        except Exception:
            return TaskOutput(task_id=task_input.task_id)


def _build_cantus_graph(soprano_notes: list, metadata: dict) -> EventGraph:
    """Build a minimal EventGraph from soprano notes for composition."""
    from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
    from bachbot.models.section import Section
    from bachbot.models.voice import Voice

    wid = metadata.get("work_id", "BENCH")
    sid = f"{wid}:section:1"
    m_start = soprano_notes[0].measure_number if soprano_notes else 1
    m_end = soprano_notes[-1].measure_number if soprano_notes else 1

    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id=wid,
            work_id=wid,
            source_format="benchmark",
            meter=metadata.get("meter", "4/4"),
        ),
        section=Section(
            section_id=sid,
            work_id=wid,
            label="Benchmark cantus",
            section_type="cantus",
            measure_start=m_start,
            measure_end=m_end,
        ),
        voices=[Voice(voice_id="Soprano:1", section_id=sid, part_name="Soprano", normalized_voice_name="Soprano")],
        notes=soprano_notes,
    )
