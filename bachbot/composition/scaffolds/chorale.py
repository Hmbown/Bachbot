"""Chorale scaffold planning."""

from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class ChoralePlan(BachbotModel):
    key: str
    phrase_measures: list[int] = Field(default_factory=list)
    chord_labels: list[str] = Field(default_factory=list)
