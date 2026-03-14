"""Motif and subject models."""

from __future__ import annotations

from pydantic import Field

from .base import BachbotModel


class MotifOccurrence(BachbotModel):
    occurrence_id: str
    section_id: str
    measure_start: int
    measure_end: int
    voice_ids: list[str] = Field(default_factory=list)


class Motif(BachbotModel):
    motif_id: str
    work_id: str
    motif_type: str
    canonical_encoding: str
    source_occurrences: list[MotifOccurrence] = Field(default_factory=list)
    transformations: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    detector_provenance: list[str] = Field(default_factory=list)
