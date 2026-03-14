from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class StructuralNote(BachbotModel):
    note_id: str
    source_note_id: str
    voice_id: str
    measure: int
    onset: float
    duration: float
    pitch: str | None = None
    midi: int | None = None
    scale_degree: int | None = None
    harmony_label: str | None = None
    local_key: str | None = None
    role: str = "structural"
    parent_note_id: str | None = None


class ProlongationSpan(BachbotModel):
    span_id: str
    voice_id: str
    start_note_id: str
    end_note_id: str
    span_type: str
    scale_degrees: list[int] = Field(default_factory=list)
    harmony_label: str | None = None


class ReductionLayer(BachbotModel):
    level: str
    notes: list[StructuralNote] = Field(default_factory=list)
    spans: list[ProlongationSpan] = Field(default_factory=list)


class Urlinie(BachbotModel):
    detected: bool = False
    degrees: list[int] = Field(default_factory=list)
    note_ids: list[str] = Field(default_factory=list)
    measure_start: int | None = None
    measure_end: int | None = None
    confidence: float = 0.0


class Bassbrechung(BachbotModel):
    detected: bool = False
    degrees: list[int] = Field(default_factory=list)
    note_ids: list[str] = Field(default_factory=list)
    measure_start: int | None = None
    measure_end: int | None = None
    confidence: float = 0.0


class SchenkerianAnalysis(BachbotModel):
    encoding_id: str
    global_key: str
    foreground: ReductionLayer
    middleground: ReductionLayer
    background: ReductionLayer
    urlinie: Urlinie = Field(default_factory=Urlinie)
    bassbrechung: Bassbrechung = Field(default_factory=Bassbrechung)
