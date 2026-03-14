"""Generated composition models."""

from __future__ import annotations

from pydantic import Field

from .base import ArtifactClass, BachbotModel


class GenerationTrace(BachbotModel):
    steps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class CompositionArtifact(BachbotModel):
    artifact_id: str
    artifact_class: ArtifactClass
    parent_work_refs: list[str] = Field(default_factory=list)
    input_constraints: dict[str, str | int | float | bool] = Field(default_factory=dict)
    generation_trace: GenerationTrace = Field(default_factory=GenerationTrace)
    validation_refs: list[str] = Field(default_factory=list)
    license: str = "generated"
    labels_for_display: list[str] = Field(default_factory=list)
    exports: list[str] = Field(default_factory=list)
