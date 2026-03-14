"""Constraint-first composition services."""

from __future__ import annotations

from bachbot.composition.scaffolds.chorale import ChoralePlan
from bachbot.composition.validators.hard_rules import validate_graph
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import ArtifactClass
from bachbot.models.composition import CompositionArtifact, GenerationTrace
from bachbot.plugins.registry import get_plugin_registry


def _chord_labels_from_trace(trace: list[str]) -> list[str]:
    labels: list[str] = []
    for step in trace:
        if ": " in step and step.startswith("m"):
            labels.append(step.rsplit(": ", 1)[-1])
    return labels


def plan_chorale(cantus: EventGraph, bundle: dict | None = None) -> ChoralePlan:
    generator = get_plugin_registry().get_generator("bachbot.chorale_harmonizer")
    generated, trace = generator.generate(cantus, artifact_id="chorale_plan_preview", bundle=bundle)
    del generated
    return ChoralePlan(
        key=(cantus.metadata.key_estimate.tonic if cantus.metadata.key_estimate else "C"),
        phrase_measures=[max((note.measure_number for note in cantus.pitch_events()), default=1)],
        chord_labels=_chord_labels_from_trace(trace),
    )


def compose_chorale_study(cantus: EventGraph, bundle: dict | None = None) -> tuple[EventGraph, CompositionArtifact, dict]:
    generator = get_plugin_registry().get_generator("bachbot.chorale_harmonizer")
    plan = plan_chorale(cantus, bundle=bundle)
    graph, trace = generator.generate(cantus, artifact_id="chorale_study_1", bundle=bundle)
    validation = validate_graph(graph)
    artifact = CompositionArtifact(
        artifact_id=f"ART-{cantus.work_id}-chorale-study",
        artifact_class=ArtifactClass.CHORALE_STUDY,
        parent_work_refs=[cantus.work_id],
        input_constraints={"mode": "chorale-study", "key": plan.key},
        generation_trace=GenerationTrace(
            steps=[
                "estimated key from cantus",
                "assigned triads to soprano events",
                "realized SATB voicings",
                "validated output with SATB rules",
            ],
            assumptions=["major-mode heuristic", "block-chord realization"],
        ),
        validation_refs=[validation.validation_id],
        labels_for_display=["Bachbot chorale study", "Generated", "Not authentic Bach"],
    )
    return graph, artifact, {"plan": plan.model_dump(mode="json"), "validation": validation.model_dump(mode="json"), "trace": trace}
