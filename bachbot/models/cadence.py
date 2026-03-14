from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class Cadence(BachbotModel):
    cadence_id: str
    ref_id: str
    cadence_type: str
    type_candidates: list[str] = Field(default_factory=list)
    key_before: str | None = None
    key_after: str | None = None
    bass_formula: str | None = None
    soprano_formula: str | None = None
    strength: float = 0.0
    voice_leading_evidence: list[str] = Field(default_factory=list)
    detector_confidence: float = 0.0

