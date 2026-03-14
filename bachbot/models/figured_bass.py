from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class FiguredBassEvent(BachbotModel):
    onset: float
    measure_number: int
    bass_pitch: str | None = None
    figures: list[str] = Field(default_factory=list)
    figure_summary: str = ""
    harmonic_event_id: str | None = None
    roman_numeral: str | None = None


class FiguredBassLine(BachbotModel):
    work_id: str
    encoding_id: str
    events: list[FiguredBassEvent] = Field(default_factory=list)
