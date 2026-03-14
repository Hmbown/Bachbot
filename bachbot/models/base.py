from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BachbotModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class CatalogIdentifier(BachbotModel):
    scheme: str
    value: str
    revision: str | None = None
    source: str | None = None


class DateRange(BachbotModel):
    start: date | None = None
    end: date | None = None
    circa: bool = False


class ExternalRef(BachbotModel):
    source: str
    value: str
    url: str | None = None


class MeasureSpan(BachbotModel):
    measure_start: int
    measure_end: int
    beat_start: float = 1.0
    beat_end: float | None = None


class KeyEstimate(BachbotModel):
    tonic: str
    mode: str
    confidence: float = 0.5


class EvidenceStatus(StrEnum):
    SUPPORTED_FACT = "supported_fact"
    INFERENCE = "inference"
    SPECULATION = "speculation"
    DISPUTED = "disputed"


ClaimStatus = EvidenceStatus


class ClaimMethod(StrEnum):
    RULE = "rule"
    HUMAN = "human"
    LLM = "llm"
    HYBRID = "hybrid"


class AuthenticityStatus(StrEnum):
    AUTHENTIC = "authentic"
    DOUBTFUL = "doubtful"
    SPURIOUS = "spurious"
    FRAGMENT = "fragment"
    LOST = "lost"
    RECONSTRUCTION_TARGET = "reconstruction_target"
    VARIANT_RELATED = "variant_related"
    NEWLY_ADDED = "newly_added"
    CONTEXTUAL_ONLY = "contextual_only"


class ArtifactClass(StrEnum):
    BACHBOT_STUDY = "bachbot-study"
    CHORALE_STUDY = "bachbot-study"
    BACHBOT_CONTINUATION = "bachbot-continuation"
    BACHBOT_RECONSTRUCTION = "bachbot-reconstruction-hypothesis"
    BACHBOT_WHAT_IF = "bachbot-what-if"
    BACHBOT_BACH_INSPIRED = "bachbot-bach-inspired"


class TypedNote(BachbotModel):
    pitch: str | None = None
    midi: int | None = None
    duration_quarters: float
    offset_quarters: float
    measure_number: int
    beat: float
    voice_id: str
    staff_id: str | None = None
    part_name: str | None = None
    tie_start: bool = False
    tie_stop: bool = False
    is_rest: bool = False
    accidental: str | None = None
    lyric: str | None = None
    fermata: bool = False
    articulations: list[str] = Field(default_factory=list)
    source_ref: str | None = None

    @property
    def onset(self) -> float:
        return self.offset_quarters

    @property
    def duration(self) -> float:
        return self.duration_quarters

    @property
    def pitch_midi(self) -> int | None:
        return self.midi

    @property
    def pitch_name(self) -> str | None:
        return self.pitch

    @property
    def event_id(self) -> str:
        return self.source_ref or f"{self.voice_id}:{self.measure_number}:{int(self.offset_quarters * 100)}"


class DumpMixin:
    def as_dict(self) -> dict[str, Any]:
        if isinstance(self, BaseModel):
            return self.model_dump(mode="json", exclude_none=True)
        raise TypeError("DumpMixin requires a Pydantic BaseModel subclass")

