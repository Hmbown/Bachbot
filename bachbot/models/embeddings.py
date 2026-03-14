from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class EmbeddingNeighbor(BachbotModel):
    label: str
    similarity: float


class ChordEmbeddingSummary(BachbotModel):
    label: str
    frequency: int
    nearest_neighbors: list[EmbeddingNeighbor] = Field(default_factory=list)


class ChoraleProjectionPoint(BachbotModel):
    work_id: str
    encoding_id: str
    key: str | None = None
    key_mode: str | None = None
    key_tonic: str | None = None
    projection_2d: list[float] = Field(default_factory=list)


class EmbeddingDiagnostics(BachbotModel):
    related_pair: str
    related_similarity: float
    unrelated_pair: str
    unrelated_similarity: float
    mode_centroid_separation: float = 0.0
    mode_within_cluster_spread: float = 0.0
    mode_separation_ratio: float = 0.0


class EmbeddingExportManifest(BachbotModel):
    dataset_id: str
    dimension: int
    context_window: int
    corpus_size: int
    chord_type_count: int
    projection_method: str
    diagnostics: EmbeddingDiagnostics
    chords: list[ChordEmbeddingSummary] = Field(default_factory=list)
    chorales: list[ChoraleProjectionPoint] = Field(default_factory=list)
    chord_vectors_path: str
    chorale_vectors_path: str
    chorale_projection_path: str
    chord_labels_path: str
    chorale_metadata_path: str
    manifest_path: str
    visualization_path: str | None = None
