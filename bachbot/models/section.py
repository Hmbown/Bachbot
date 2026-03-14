from __future__ import annotations

from bachbot.models.base import BachbotModel


class Section(BachbotModel):
    section_id: str
    work_id: str
    parent_section_id: str | None = None
    label: str
    section_type: str
    tempo_marking: str | None = None
    key_signature_context: str | None = None
    meter_context: str | None = None
    measure_start: int
    measure_end: int

