from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class Hypothesis(BachbotModel):
    hypothesis_id: str
    title: str
    phenomenon_description: str
    scope: str
    supporting_claim_refs: list[str] = Field(default_factory=list)
    competing_explanations: list[str] = Field(default_factory=list)
    test_plan: list[str] = Field(default_factory=list)
    falsifiers: list[str] = Field(default_factory=list)
    status: str = "open"

