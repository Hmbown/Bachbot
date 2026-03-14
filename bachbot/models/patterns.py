from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class PatternOccurrence(BachbotModel):
    work_id: str
    encoding_id: str
    mode: str
    start_ref_id: str
    end_ref_id: str
    start_measure: int
    end_measure: int
    start_onset: float
    end_onset: float
    global_key: str | None = None
    local_keys: list[str] = Field(default_factory=list)


class PatternStats(BachbotModel):
    pattern_id: str
    ngram: int
    pattern: str
    labels: list[str] = Field(default_factory=list)
    count: int
    work_count: int
    support: float = 0.0
    expected_count: float = 0.0
    pmi: float = 0.0
    null_mean_count: float = 0.0
    null_p95_count: float = 0.0
    null_mean_work_count: float = 0.0
    null_p95_work_count: float = 0.0
    significant: bool = False
    occurrences: list[PatternOccurrence] = Field(default_factory=list)


class CorpusPatternIndex(BachbotModel):
    dataset_id: str
    ngram: int
    corpus_size: int
    total_windows: int
    label_vocabulary_size: int
    generated_at: str
    patterns: list[PatternStats] = Field(default_factory=list)
