from __future__ import annotations

from pydantic import BaseModel


class FugueScaffold(BaseModel):
    key: str
    voices: int
    answer_type: str = "auto"
    countersubject: bool = True
    episode_count: int = 2

