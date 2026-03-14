"""Evaluation and validation models."""

from __future__ import annotations

from pydantic import Field

from .base import BachbotModel


class ValidationIssue(BachbotModel):
    code: str
    severity: str
    message: str
    measure: int | None = None
    voice_ids: list[str] = Field(default_factory=list)


class ValidationReport(BachbotModel):
    validation_id: str
    subject_type: str
    subject_id: str
    passed: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class EvaluationResult(BachbotModel):
    evaluation_id: str
    subject_type: str
    subject_id: str
    metric_name: str
    metric_value: float
    rubric_level: str | None = None
    human_or_machine: str = "machine"
    notes: list[str] = Field(default_factory=list)
    timestamp: str
