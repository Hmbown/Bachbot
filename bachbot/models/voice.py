from __future__ import annotations

from bachbot.models.base import BachbotModel


class Voice(BachbotModel):
    voice_id: str
    section_id: str
    staff_id: str | None = None
    part_name: str | None = None
    normalized_voice_name: str
    instrument_or_role: str | None = None
    range_profile: tuple[int, int] | None = None
    clef_profile: str | None = None

