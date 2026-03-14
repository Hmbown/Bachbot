"""Data models for the human evaluation protocol."""

from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class EvaluationPair(BachbotModel):
    """A randomized A/B pair of one original and one generated chorale."""

    pair_id: str
    chorale_a_id: str
    chorale_b_id: str
    chorale_a_is_original: bool
    chorale_a_midi_path: str
    chorale_b_midi_path: str


class EvaluationRating(BachbotModel):
    """A single evaluator's ratings for one A/B pair."""

    pair_id: str
    evaluator_id: str
    timestamp: str  # ISO format
    musicality_a: int = Field(ge=1, le=7)
    musicality_b: int = Field(ge=1, le=7)
    authenticity_a: int = Field(ge=1, le=7)
    authenticity_b: int = Field(ge=1, le=7)
    voice_leading_a: int = Field(ge=1, le=7)
    voice_leading_b: int = Field(ge=1, le=7)
    identified_original: str  # "a", "b", or "unsure"
    notes: str = ""


class EvaluationSession(BachbotModel):
    """An evaluation session for one evaluator across multiple pairs."""

    session_id: str
    evaluator_id: str
    pairs: list[EvaluationPair] = Field(default_factory=list)
    ratings: list[EvaluationRating] = Field(default_factory=list)


class EvaluationSummary(BachbotModel):
    """Aggregated summary statistics across all evaluation sessions."""

    total_pairs: int = 0
    total_evaluators: int = 0
    total_ratings: int = 0
    avg_musicality_original: float = 0.0
    avg_musicality_generated: float = 0.0
    avg_authenticity_original: float = 0.0
    avg_authenticity_generated: float = 0.0
    avg_voice_leading_original: float = 0.0
    avg_voice_leading_generated: float = 0.0
    identification_accuracy: float = 0.0
    krippendorff_alpha: float = 0.0
