from __future__ import annotations

from pydantic import BaseModel


class CanonScaffold(BaseModel):
    key: str
    delay_beats: int = 2
    interval_of_imitation: str = "P5"
    strictness: str = "strict"

