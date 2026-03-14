from __future__ import annotations

from pydantic import BaseModel


class InventionScaffold(BaseModel):
    key: str
    voices: int = 2
    phrase_count: int = 4
    motif_strategy: str = "economy-first"

