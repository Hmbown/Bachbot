from __future__ import annotations

import builtins
import importlib
import json
import math
import warnings
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from bachbot.analysis.stats.patterns import load_corpus_bundles
from bachbot.exports.json_export import write_json
from bachbot.models.embeddings import (
    ChoraleProjectionPoint,
    ChordEmbeddingSummary,
    EmbeddingDiagnostics,
    EmbeddingExportManifest,
    EmbeddingNeighbor,
)
from bachbot.registry.storage import BachbotStorage


@dataclass(slots=True)
class TrainedEmbeddingSpace:
    dataset_id: str
    dimension: int
    context_window: int
    corpus_size: int
    projection_method: str
    chord_labels: list[str]
    chord_counts: dict[str, int]
    chord_vectors: np.ndarray
    chorale_vectors: np.ndarray
    chorale_projection: np.ndarray
    chorale_metadata: list[dict[str, str | None]]
    diagnostics: EmbeddingDiagnostics


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _ordered_harmony(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    harmony = bundle.get("deterministic_findings", {}).get("harmony", [])
    return sorted(
        harmony,
        key=lambda event: (
            float(event.get("onset", 0.0)),
            str(event.get("harmonic_event_id", "")),
            str(event.get("ref_id", "")),
        ),
    )


def _extract_roman_sequence(bundle: dict[str, Any], *, collapse_repeats: bool = True) -> list[str]:
    sequence: list[str] = []
    previous_label: str | None = None
    for event in _ordered_harmony(bundle):
        candidates = event.get("roman_numeral_candidate_set") or []
        if not candidates:
            continue
        label = str(candidates[0])
        if collapse_repeats and label == previous_label:
            continue
        sequence.append(label)
        previous_label = label
    return sequence


def _row_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-9)


def _ensure_dimension(matrix: np.ndarray, dimension: int) -> np.ndarray:
    if matrix.shape[1] >= dimension:
        return matrix[:, :dimension]
    padding = np.zeros((matrix.shape[0], dimension - matrix.shape[1]), dtype=matrix.dtype)
    return np.hstack((matrix, padding))


def _cooccurrence_matrix(
    sequences: Sequence[Sequence[str]],
    vocabulary: Sequence[str],
    *,
    context_window: int,
) -> np.ndarray:
    index = {label: position for position, label in enumerate(vocabulary)}
    matrix = np.zeros((len(vocabulary), len(vocabulary)), dtype=np.float64)
    for sequence in sequences:
        for position, label in enumerate(sequence):
            row = index[label]
            start = max(0, position - context_window)
            stop = min(len(sequence), position + context_window + 1)
            for neighbor_position in range(start, stop):
                if neighbor_position == position:
                    continue
                weight = 1.0 / abs(neighbor_position - position)
                column = index[sequence[neighbor_position]]
                matrix[row, column] += weight
    return matrix


def _ppmi_embeddings(
    sequences: Sequence[Sequence[str]],
    vocabulary: Sequence[str],
    *,
    dimension: int,
    context_window: int,
) -> np.ndarray:
    cooccurrence = _cooccurrence_matrix(sequences, vocabulary, context_window=context_window)
    total = max(float(cooccurrence.sum()), 1e-9)
    row_totals = cooccurrence.sum(axis=1, keepdims=True)
    column_totals = cooccurrence.sum(axis=0, keepdims=True)
    expected = np.maximum((row_totals @ column_totals) / total, 1e-9)
    ratio = np.maximum(cooccurrence, 1e-9) / expected
    ppmi = np.maximum(np.log2(ratio), 0.0)
    left, singular_values, _ = np.linalg.svd(ppmi, full_matrices=False)
    usable = min(dimension, left.shape[1], singular_values.shape[0])
    dense = left[:, :usable] * np.sqrt(singular_values[:usable])
    dense = _ensure_dimension(dense.astype(np.float32), dimension)
    return _row_normalize(dense)


def _tf_idf_weights(counts: np.ndarray) -> np.ndarray:
    document_count = counts.shape[0]
    document_frequency = np.count_nonzero(counts > 0, axis=0)
    inverse_document_frequency = np.log((1 + document_count) / (1 + document_frequency)) + 1.0
    return counts * inverse_document_frequency


def _fallback_projection(vectors: np.ndarray) -> tuple[np.ndarray, str]:
    if len(vectors) == 0:
        return np.zeros((0, 2), dtype=np.float32), "empty"
    if len(vectors) == 1:
        return np.zeros((1, 2), dtype=np.float32), "linear-fallback"
    centered = vectors - vectors.mean(axis=0, keepdims=True)
    left, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
    usable = min(2, left.shape[1], singular_values.shape[0])
    projection = left[:, :usable] * singular_values[:usable]
    projection = _ensure_dimension(projection.astype(np.float32), 2)
    return projection, "linear-fallback"


# `umap.__init__` eagerly imports optional parametric UMAP support, which in
# mixed environments can drag in a broken TensorFlow stack. We only need the
# standard non-parametric reducer here, so we temporarily block TensorFlow
# imports and let umap gracefully degrade.
@lru_cache(maxsize=1)
def _load_umap_module():
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "tensorflow" or name.startswith("tensorflow."):
            raise ImportError("tensorflow intentionally disabled for non-parametric UMAP")
        return real_import(name, globals, locals, fromlist, level)

    builtins.__import__ = guarded_import
    try:
        return importlib.import_module("umap")
    finally:
        builtins.__import__ = real_import


def _project_chorales(vectors: np.ndarray) -> tuple[np.ndarray, str]:
    if len(vectors) < 4:
        return _fallback_projection(vectors)
    try:
        umap = _load_umap_module()
        reducer = umap.UMAP(
            n_components=2,
            metric="cosine",
            n_neighbors=min(20, max(2, len(vectors) - 1)),
            min_dist=0.15,
            random_state=42,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            projection = reducer.fit_transform(vectors)
        return projection.astype(np.float32), "umap"
    except Exception:
        return _fallback_projection(vectors)


def _mode_cluster_metrics(
    projection: np.ndarray,
    chorale_metadata: Sequence[dict[str, str | None]],
) -> tuple[float, float, float]:
    if len(projection) == 0:
        return 0.0, 0.0, 0.0
    major = projection[[index for index, item in enumerate(chorale_metadata) if item.get("key_mode") == "major"]]
    minor = projection[[index for index, item in enumerate(chorale_metadata) if item.get("key_mode") == "minor"]]
    if len(major) == 0 or len(minor) == 0:
        return 0.0, 0.0, 0.0
    major_centroid = major.mean(axis=0)
    minor_centroid = minor.mean(axis=0)
    separation = float(np.linalg.norm(major_centroid - minor_centroid))
    within_major = float(np.mean(np.linalg.norm(major - major_centroid, axis=1))) if len(major) else 0.0
    within_minor = float(np.mean(np.linalg.norm(minor - minor_centroid, axis=1))) if len(minor) else 0.0
    spread = (within_major + within_minor) / 2.0
    ratio = separation / max(spread, 1e-9)
    return separation, spread, ratio


def _cosine_similarity(labels: Sequence[str], vectors: np.ndarray, left: str, right: str) -> float:
    index = {label: position for position, label in enumerate(labels)}
    if left not in index or right not in index:
        return 0.0
    return float(vectors[index[left]] @ vectors[index[right]])


def _nearest_neighbors(
    label: str,
    labels: Sequence[str],
    vectors: np.ndarray,
    *,
    limit: int = 5,
) -> list[EmbeddingNeighbor]:
    index = {item: position for position, item in enumerate(labels)}
    if label not in index:
        return []
    anchor = index[label]
    similarities = vectors @ vectors[anchor]
    ordered = sorted(
        (
            (labels[position], float(score))
            for position, score in enumerate(similarities)
            if position != anchor
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    return [EmbeddingNeighbor(label=neighbor, similarity=round(score, 4)) for neighbor, score in ordered[:limit]]


def build_embedding_space(
    corpus: Sequence[dict[str, Any]],
    *,
    dataset_id: str = "unknown",
    dimension: int = 32,
    context_window: int = 2,
    collapse_repeats: bool = True,
) -> TrainedEmbeddingSpace:
    chorale_metadata: list[dict[str, str | None]] = []
    sequences: list[list[str]] = []
    for bundle in corpus:
        sequence = _extract_roman_sequence(bundle, collapse_repeats=collapse_repeats)
        if not sequence:
            continue
        metadata = bundle.get("metadata", {})
        chorale_metadata.append(
            {
                "work_id": bundle.get("work_id", ""),
                "encoding_id": metadata.get("encoding_id", bundle.get("work_id", "")),
                "key": metadata.get("key"),
                "key_mode": metadata.get("key_mode"),
                "key_tonic": metadata.get("key_tonic"),
            }
        )
        sequences.append(sequence)

    vocabulary = sorted({label for sequence in sequences for label in sequence})
    chord_counts: Counter[str] = Counter(label for sequence in sequences for label in sequence)
    chord_vectors = _ppmi_embeddings(
        sequences,
        vocabulary,
        dimension=dimension,
        context_window=context_window,
    )

    counts = np.zeros((len(sequences), len(vocabulary)), dtype=np.float32)
    index = {label: position for position, label in enumerate(vocabulary)}
    for row, sequence in enumerate(sequences):
        for label in sequence:
            counts[row, index[label]] += 1.0
    chorale_vectors = _row_normalize(_tf_idf_weights(counts) @ chord_vectors).astype(np.float32)
    projection, projection_method = _project_chorales(chorale_vectors)
    mode_separation, mode_spread, mode_ratio = _mode_cluster_metrics(projection, chorale_metadata)
    diagnostics = EmbeddingDiagnostics(
        related_pair="V~V7",
        related_similarity=round(_cosine_similarity(vocabulary, chord_vectors, "V", "V7"), 4),
        unrelated_pair="V~ii",
        unrelated_similarity=round(_cosine_similarity(vocabulary, chord_vectors, "V", "ii"), 4),
        mode_centroid_separation=round(mode_separation, 4),
        mode_within_cluster_spread=round(mode_spread, 4),
        mode_separation_ratio=round(mode_ratio, 4),
    )
    return TrainedEmbeddingSpace(
        dataset_id=dataset_id,
        dimension=dimension,
        context_window=context_window,
        corpus_size=len(sequences),
        projection_method=projection_method,
        chord_labels=vocabulary,
        chord_counts=dict(chord_counts),
        chord_vectors=chord_vectors,
        chorale_vectors=chorale_vectors,
        chorale_projection=projection,
        chorale_metadata=chorale_metadata,
        diagnostics=diagnostics,
    )


def _render_visualization(
    dataset_id: str,
    projection: np.ndarray,
    chorale_metadata: Sequence[dict[str, str | None]],
    projection_method: str,
    output_path: Path,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"major": "#1f77b4", "minor": "#d62728"}
    figure, axes = plt.subplots(figsize=(10, 7))
    for mode in ("major", "minor"):
        indexes = [index for index, item in enumerate(chorale_metadata) if item.get("key_mode") == mode]
        if not indexes:
            continue
        points = projection[indexes]
        axes.scatter(points[:, 0], points[:, 1], label=mode, alpha=0.75, s=28, c=colors[mode])
    unknown_indexes = [
        index for index, item in enumerate(chorale_metadata) if item.get("key_mode") not in {"major", "minor"}
    ]
    if unknown_indexes:
        points = projection[unknown_indexes]
        axes.scatter(points[:, 0], points[:, 1], label="unknown", alpha=0.5, s=24, c="#7f7f7f")
    axes.set_title(f"{dataset_id} chorale embedding space ({projection_method})")
    axis_prefix = "UMAP" if projection_method == "umap" else "Component"
    axes.set_xlabel(f"{axis_prefix}-1")
    axes.set_ylabel(f"{axis_prefix}-2")
    axes.legend(loc="best")
    axes.grid(alpha=0.2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=200)
    plt.close(figure)
    return output_path


def export_embedding_space(
    space: TrainedEmbeddingSpace,
    *,
    output_dir: Path,
    visualize: bool = False,
) -> EmbeddingExportManifest:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    chord_vectors_path = output_dir / f"chord_embeddings.{space.dimension}d.npy"
    chorale_vectors_path = output_dir / f"chorale_embeddings.{space.dimension}d.npy"
    chorale_projection_path = output_dir / f"chorale_projection.{space.projection_method}.npy"
    chord_labels_path = output_dir / "chord_labels.json"
    chorale_metadata_path = output_dir / "chorale_metadata.json"
    manifest_path = output_dir / f"embedding_space.{space.dimension}d.json"
    visualization_path = output_dir / f"chorale_embedding_space.{space.projection_method}.png"

    np.save(chord_vectors_path, space.chord_vectors.astype(np.float32))
    np.save(chorale_vectors_path, space.chorale_vectors.astype(np.float32))
    np.save(chorale_projection_path, space.chorale_projection.astype(np.float32))
    write_json(
        {
            "generated_at": _timestamp(),
            "dimension": space.dimension,
            "labels": space.chord_labels,
        },
        chord_labels_path,
    )
    write_json(
        {
            "generated_at": _timestamp(),
            "chorales": list(space.chorale_metadata),
        },
        chorale_metadata_path,
    )
    if visualize:
        _render_visualization(
            space.dataset_id,
            space.chorale_projection,
            space.chorale_metadata,
            space.projection_method,
            visualization_path,
        )

    chords = [
        ChordEmbeddingSummary(
            label=label,
            frequency=int(space.chord_counts.get(label, 0)),
            nearest_neighbors=_nearest_neighbors(label, space.chord_labels, space.chord_vectors),
        )
        for label in space.chord_labels
    ]
    chorales = [
        ChoraleProjectionPoint(
            work_id=str(metadata.get("work_id", "")),
            encoding_id=str(metadata.get("encoding_id", "")),
            key=metadata.get("key"),
            key_mode=metadata.get("key_mode"),
            key_tonic=metadata.get("key_tonic"),
            projection_2d=[
                round(float(space.chorale_projection[index, 0]), 4),
                round(float(space.chorale_projection[index, 1]), 4),
            ],
        )
        for index, metadata in enumerate(space.chorale_metadata)
    ]
    manifest = EmbeddingExportManifest(
        dataset_id=space.dataset_id,
        dimension=space.dimension,
        context_window=space.context_window,
        corpus_size=space.corpus_size,
        chord_type_count=len(space.chord_labels),
        projection_method=space.projection_method,
        diagnostics=space.diagnostics,
        chords=chords,
        chorales=chorales,
        chord_vectors_path=str(chord_vectors_path),
        chorale_vectors_path=str(chorale_vectors_path),
        chorale_projection_path=str(chorale_projection_path),
        chord_labels_path=str(chord_labels_path),
        chorale_metadata_path=str(chorale_metadata_path),
        manifest_path=str(manifest_path),
        visualization_path=str(visualization_path) if visualize else None,
    )
    write_json(manifest.model_dump(mode="json"), manifest_path)
    return manifest


def analyze_dataset_embeddings(
    *,
    dataset: str = "dcml_bach_chorales",
    dimension: int = 32,
    context_window: int = 2,
    output_dir: Path | None = None,
    visualize: bool = False,
    collapse_repeats: bool = True,
) -> EmbeddingExportManifest:
    corpus = load_corpus_bundles(dataset)
    space = build_embedding_space(
        corpus,
        dataset_id=dataset,
        dimension=dimension,
        context_window=context_window,
        collapse_repeats=collapse_repeats,
    )
    if output_dir is None:
        storage = BachbotStorage(dataset).ensure()
        output_dir = Path(storage.derived_dir) / "embeddings"
    return export_embedding_space(space, output_dir=output_dir, visualize=visualize)
