from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel, EvidenceStatus
from bachbot.models.refs import PassageRef


class AnnotationSource(BachbotModel):
    source_id: str
    source_type: str
    label: str
    version: str | None = None
    provenance: list[str] = Field(default_factory=list)


class AnnotatedFinding(BachbotModel):
    finding_id: str
    finding_type: str
    passage_ref: PassageRef
    value: dict[str, object] = Field(default_factory=dict)
    status: EvidenceStatus = EvidenceStatus.SUPPORTED_FACT
    confidence: float = 0.0
    source_id: str


class AnnotationLayer(BachbotModel):
    layer_id: str
    work_id: str
    section_id: str
    source: AnnotationSource
    findings: list[AnnotatedFinding] = Field(default_factory=list)


class AnnotationAgreement(BachbotModel):
    passage_ref: PassageRef
    finding_type: str
    value: dict[str, object] = Field(default_factory=dict)
    left_source: str
    right_source: str


class AnnotationConflict(BachbotModel):
    passage_ref: PassageRef
    finding_type: str
    left_value: dict[str, object] = Field(default_factory=dict)
    right_value: dict[str, object] = Field(default_factory=dict)
    left_source: str
    right_source: str
    severity: str = "warning"


class AnnotationFindingTypeSummary(BachbotModel):
    match_count: int = 0
    conflict_count: int = 0
    left_only_count: int = 0
    right_only_count: int = 0


class AnnotationDiffSummary(BachbotModel):
    match_count: int = 0
    conflict_count: int = 0
    left_only_count: int = 0
    right_only_count: int = 0
    overlap_count: int = 0
    agreement_ratio: float = 0.0
    by_finding_type: dict[str, AnnotationFindingTypeSummary] = Field(default_factory=dict)


class AnnotationDiff(BachbotModel):
    left_source: AnnotationSource
    right_source: AnnotationSource
    matches: list[AnnotationAgreement] = Field(default_factory=list)
    conflicts: list[AnnotationConflict] = Field(default_factory=list)
    left_only: list[AnnotatedFinding] = Field(default_factory=list)
    right_only: list[AnnotatedFinding] = Field(default_factory=list)
    summary: AnnotationDiffSummary = Field(default_factory=AnnotationDiffSummary)
