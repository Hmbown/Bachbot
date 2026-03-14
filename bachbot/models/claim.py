"""Analytical claim models."""

from __future__ import annotations

from pydantic import Field

from .base import BachbotModel, ClaimStatus


class EvidenceRef(BachbotModel):
    ref_id: str
    description: str


class AnalyticalClaim(BachbotModel):
    claim_id: str
    claim_type: str
    lens: str
    statement: str
    status: ClaimStatus
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    method: str = "rule"
    confidence: float = 0.0
    counterarguments: list[str] = Field(default_factory=list)
    created_by: str = "bachbot"
