"""Harmonic event models."""

from __future__ import annotations

from pydantic import Field

from .base import BachbotModel


class RomanNumeralCandidate(BachbotModel):
    symbol: str
    confidence: float


class HarmonicEvent(BachbotModel):
    harmonic_event_id: str
    ref_id: str
    onset: float
    duration: float
    verticality_class: str
    local_key: str | None = None
    global_key: str | None = None
    roman_numeral_candidate_set: list[str] = Field(default_factory=list)
    figured_bass_like_summary: str | None = None
    nonharmonic_tone_tags: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    method: str = "rule"
