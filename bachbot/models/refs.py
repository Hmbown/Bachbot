from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class PassageRef(BachbotModel):
    measure_start: int
    measure_end: int
    voice_ids: list[str] = Field(default_factory=list)


class MeasureRangeReference(BachbotModel):
    ref_id: str
    work_id: str
    section_id: str
    source_or_encoding_id: str
    measure_number_notated: int
    measure_number_logical: int
    beat_start: float = 1.0
    beat_end: float | None = None
    voice_ids: list[str] = Field(default_factory=list)
    variant_map: dict[str, str] = Field(default_factory=dict)


RangeReference = MeasureRangeReference

