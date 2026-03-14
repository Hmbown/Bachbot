from __future__ import annotations

from pydantic import BaseModel


class PreludeScaffold(BaseModel):
    key: str
    figuration_type: str = "broken-chord"
    cadence_count: int = 4
    length_measures: int = 16

