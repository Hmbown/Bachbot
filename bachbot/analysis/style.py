"""Style fingerprinting and anomaly detection for authorship/style analysis.

Computes per-chorale feature vectors from EvidenceBundle data, compares
fingerprints via cosine similarity and Euclidean distance, and flags
stylistic outliers via z-score anomaly detection.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import Field

from bachbot.models.base import BachbotModel


# ── Models ───────────────────────────────────────────────────────────────


class StyleFingerprint(BachbotModel):
    work_id: str
    feature_count: int = 0
    features: dict[str, float] = Field(default_factory=dict)


class FeatureDiff(BachbotModel):
    name: str
    left_value: float
    right_value: float
    difference: float


class StyleComparison(BachbotModel):
    left_work_id: str
    right_work_id: str
    cosine_similarity: float
    euclidean_distance: float
    most_different: list[FeatureDiff] = Field(default_factory=list)
    most_similar: list[FeatureDiff] = Field(default_factory=list)


class AnomalyReport(BachbotModel):
    work_id: str
    anomaly_score: float
    outlier_features: list[FeatureDiff] = Field(default_factory=list)
    nearest_neighbors: list[tuple[str, float]] = Field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────────────


def _safe_div(a: float, b: float) -> float:
    return a / b if b != 0 else 0.0


def _shannon_entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    return -sum(
        (c / total) * math.log2(c / total) for c in counts if c > 0
    )


# ── Feature extraction ──────────────────────────────────────────────────


def compute_style_fingerprint(bundle: Any) -> StyleFingerprint:
    """Extract 30+ style features from an EvidenceBundle (or dict).

    Parameters
    ----------
    bundle : EvidenceBundle | dict
        The evidence bundle to fingerprint.  Accepts either a Pydantic model
        (with ``model_dump``) or a plain dict (e.g. loaded from JSON).

    Returns
    -------
    StyleFingerprint
    """
    if hasattr(bundle, "model_dump"):
        bundle = bundle.model_dump(mode="json")

    work_id: str = bundle.get("work_id", "unknown")
    findings: dict = bundle.get("deterministic_findings", {})
    metadata: dict = bundle.get("metadata", {})
    harmony: list[dict] = findings.get("harmony", [])
    cadences_raw: list[dict] = findings.get("cadences", [])
    phrase_endings: list[dict] = findings.get("phrase_endings", [])
    vl: dict = findings.get("voice_leading", {})
    counterpoint: dict = vl.get("counterpoint", {}) if isinstance(vl, dict) else {}
    modulation_graph: dict | None = findings.get("modulation_graph")
    distributions: dict = findings.get("distributions", {})

    features: dict[str, float] = {}

    # ── 1. Harmonic vocabulary ───────────────────────────────────────────

    chord_counts: Counter[str] = Counter()
    for h in harmony:
        candidates = h.get("roman_numeral_candidate_set", [])
        if candidates:
            chord_counts[candidates[0]] += 1

    total_chords = sum(chord_counts.values())

    features["unique_chord_count"] = float(len(chord_counts))
    features["chord_entropy"] = _shannon_entropy(list(chord_counts.values()))

    dom_count = chord_counts.get("V", 0) + chord_counts.get("V7", 0)
    features["dominant_chord_ratio"] = _safe_div(dom_count, total_chords)

    sec_dom_count = sum(v for k, v in chord_counts.items() if "/" in k)
    features["secondary_dom_ratio"] = _safe_div(sec_dom_count, total_chords)

    _SEVENTH_LABELS = {"V7", "viiø7", "viio7", "ii7", "IV7", "vi7", "iv7", "VI7", "iiø7"}
    seventh_count = sum(chord_counts.get(s, 0) for s in _SEVENTH_LABELS)
    features["seventh_chord_ratio"] = _safe_div(seventh_count, total_chords)

    features["tonic_ratio"] = _safe_div(
        chord_counts.get("I", 0) + chord_counts.get("i", 0), total_chords
    )
    features["subdominant_ratio"] = _safe_div(
        chord_counts.get("IV", 0) + chord_counts.get("iv", 0), total_chords
    )

    # ── 2. Cadence patterns ──────────────────────────────────────────────

    all_cadences = cadences_raw + phrase_endings
    features["cadence_count"] = float(len(all_cadences))

    cad_types = Counter(
        c.get("cadence_type", c.get("type", "")) for c in all_cadences
    )
    total_cad = len(all_cadences) or 1
    features["pac_ratio"] = _safe_div(cad_types.get("PAC", 0), total_cad)
    features["hc_ratio"] = _safe_div(cad_types.get("HC", 0), total_cad)
    features["iac_ratio"] = _safe_div(cad_types.get("IAC", 0), total_cad)
    features["dc_ratio"] = _safe_div(cad_types.get("DC", 0), total_cad)

    # Measure count heuristic: from passage_refs or harmony events
    passage_refs = bundle.get("passage_refs", [])
    if passage_refs:
        measures = [
            r.get("measure_start", r.get("measure_number_logical", 0))
            for r in passage_refs
        ]
        measure_count = max(measures) if measures else 0
    elif harmony:
        # Infer from harmony ref_ids or onsets
        measure_count = 0
        for h in harmony:
            ref = h.get("ref_id", "")
            if ":m" in ref:
                try:
                    m = int(ref.split(":m")[-1])
                    measure_count = max(measure_count, m)
                except ValueError:
                    pass
        if measure_count == 0:
            # Fallback: rough onset-based estimate (4 quarter-notes per measure)
            max_onset = max((h.get("onset", 0) for h in harmony), default=0)
            measure_count = max(1, int(max_onset / 4) + 1)
    else:
        measure_count = 0

    features["cadence_density"] = _safe_div(len(all_cadences), max(measure_count, 1))

    # ── 3. Voice-leading ─────────────────────────────────────────────────

    features["parallel_violation_count"] = float(
        (counterpoint.get("parallel_5ths", 0) or 0)
        + (counterpoint.get("parallel_8ves", 0) or 0)
    )

    total_motion = (
        (vl.get("contrary", 0) or 0)
        + (vl.get("similar", 0) or 0)
        + (vl.get("oblique", 0) or 0)
        + (vl.get("parallel", 0) or 0)
    ) if isinstance(vl, dict) else 0
    features["contrary_motion_ratio"] = _safe_div(
        vl.get("contrary", 0) if isinstance(vl, dict) else 0, max(total_motion, 1)
    )
    features["similar_motion_ratio"] = _safe_div(
        vl.get("similar", 0) if isinstance(vl, dict) else 0, max(total_motion, 1)
    )
    features["oblique_motion_ratio"] = _safe_div(
        vl.get("oblique", 0) if isinstance(vl, dict) else 0, max(total_motion, 1)
    )
    features["parallel_motion_ratio"] = _safe_div(
        vl.get("parallel", 0) if isinstance(vl, dict) else 0, max(total_motion, 1)
    )

    features["spacing_violation_count"] = float(
        len(vl.get("spacing_issues", [])) if isinstance(vl, dict) else 0
    )
    features["range_violation_count"] = float(
        len(vl.get("range_issues", [])) if isinstance(vl, dict) else 0
    )

    # Average voice motion (from harmony intervals — approximate via chord root changes)
    # We approximate by counting how many distinct chord labels appear in consecutive pairs
    chord_labels = [
        h.get("roman_numeral_candidate_set", [""])[0]
        for h in harmony
        if h.get("roman_numeral_candidate_set")
    ]
    chord_change_count = sum(
        1 for a, b in zip(chord_labels, chord_labels[1:]) if a != b
    )
    features["avg_voice_motion"] = _safe_div(chord_change_count, max(len(chord_labels) - 1, 1))

    # ── 4. Modulation ────────────────────────────────────────────────────

    if modulation_graph and isinstance(modulation_graph, dict):
        regions = modulation_graph.get("regions", [])
        edges = modulation_graph.get("edges", [])
        features["modulation_count"] = float(len(edges))
        if edges:
            distances = [e.get("tonal_distance", 0) for e in edges]
            features["avg_tonal_distance"] = sum(distances) / len(distances)
            pivot_count = sum(
                1 for e in edges if e.get("modulation_type") == "common_chord"
            )
            features["common_chord_pivot_ratio"] = _safe_div(pivot_count, len(edges))
        else:
            features["avg_tonal_distance"] = 0.0
            features["common_chord_pivot_ratio"] = 0.0
        features["region_count"] = float(len(regions))
    else:
        # Fall back to counting distinct local keys in harmony
        local_keys = {h.get("local_key", "") for h in harmony if h.get("local_key")}
        features["modulation_count"] = float(max(len(local_keys) - 1, 0))
        features["avg_tonal_distance"] = 0.0
        features["common_chord_pivot_ratio"] = 0.0
        features["region_count"] = float(len(local_keys)) if local_keys else 1.0

    # ── 5. Melodic contour (soprano from harmony verticalities) ──────────

    # Attempt to extract soprano pitch info from harmony events
    soprano_midis: list[int] = []
    for h in harmony:
        # Some bundles may embed pitch info in verticality_class or figured_bass_like_summary
        # but the standard bundle doesn't store per-voice MIDI directly.
        # Use nonharmonic_tone_tags to detect soprano activity as a proxy.
        pass

    # If we have distributions with pitch info, use that
    pc_histogram = distributions.get("pitch_class_histogram", {})
    if pc_histogram and isinstance(pc_histogram, dict):
        pc_counts = [pc_histogram.get(str(i), 0) for i in range(12)]
        features["pitch_class_entropy"] = _shannon_entropy(pc_counts)
    else:
        features["pitch_class_entropy"] = 0.0

    # Soprano contour features — derive from harmony onset spacing as proxy
    intervals: list[float] = []
    if len(chord_labels) >= 2:
        # Direction changes in chord progression (as a proxy for melodic contour)
        onsets = [h.get("onset", 0.0) for h in harmony]
        durations = [h.get("duration", 1.0) for h in harmony]
        onset_diffs = [b - a for a, b in zip(onsets, onsets[1:]) if b > a]
        if onset_diffs:
            features["avg_soprano_interval"] = sum(onset_diffs) / len(onset_diffs)
        else:
            features["avg_soprano_interval"] = 0.0
    else:
        features["avg_soprano_interval"] = 0.0

    # Step/leap ratios — from chord change frequency as proxy
    features["soprano_step_ratio"] = _safe_div(
        len(chord_labels) - chord_change_count, max(len(chord_labels) - 1, 1)
    )
    features["soprano_leap_ratio"] = _safe_div(
        chord_change_count, max(len(chord_labels) - 1, 1)
    )

    # Direction changes — count alternations between repeating and changing chords
    direction_changes = 0
    if len(chord_labels) >= 3:
        changes = [chord_labels[i] != chord_labels[i + 1] for i in range(len(chord_labels) - 1)]
        direction_changes = sum(
            1 for a, b in zip(changes, changes[1:]) if a != b
        )
    features["soprano_direction_changes"] = float(direction_changes)

    # ── 6. General statistics ────────────────────────────────────────────

    features["measure_count"] = float(measure_count)
    features["voice_count"] = float(
        len({v for r in passage_refs for v in r.get("voice_ids", [])})
        if passage_refs else 4.0
    )
    features["note_count"] = float(total_chords)  # harmonic events as proxy
    features["avg_notes_per_measure"] = _safe_div(total_chords, max(measure_count, 1))

    # Progression diversity
    bigrams = {(a, b) for a, b in zip(chord_labels, chord_labels[1:]) if a and b}
    features["progression_bigram_count"] = float(len(bigrams))

    # Harmonic rhythm
    features["harmonic_rhythm_mean"] = _safe_div(total_chords, max(measure_count, 1))

    # Phrase count
    features["phrase_count"] = float(len(phrase_endings))

    return StyleFingerprint(
        work_id=work_id,
        feature_count=len(features),
        features=features,
    )


# ── Comparison ───────────────────────────────────────────────────────────


def compare_fingerprints(fp_a: StyleFingerprint, fp_b: StyleFingerprint) -> StyleComparison:
    """Compare two style fingerprints via cosine similarity and Euclidean distance."""
    common_keys = sorted(set(fp_a.features) & set(fp_b.features))

    if not common_keys:
        return StyleComparison(
            left_work_id=fp_a.work_id,
            right_work_id=fp_b.work_id,
            cosine_similarity=0.0,
            euclidean_distance=0.0,
        )

    vec_a = [fp_a.features[k] for k in common_keys]
    vec_b = [fp_b.features[k] for k in common_keys]

    # Cosine similarity
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    cosine = _safe_div(dot, norm_a * norm_b)

    # Euclidean distance
    euclid = math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))

    # Feature diffs
    diffs: list[FeatureDiff] = []
    for k, a, b in zip(common_keys, vec_a, vec_b):
        diffs.append(FeatureDiff(name=k, left_value=a, right_value=b, difference=a - b))

    diffs_by_abs = sorted(diffs, key=lambda d: abs(d.difference), reverse=True)
    most_different = diffs_by_abs[:5]
    most_similar = sorted(diffs, key=lambda d: abs(d.difference))[:5]

    return StyleComparison(
        left_work_id=fp_a.work_id,
        right_work_id=fp_b.work_id,
        cosine_similarity=round(cosine, 6),
        euclidean_distance=round(euclid, 6),
        most_different=most_different,
        most_similar=most_similar,
    )


# ── Anomaly detection ────────────────────────────────────────────────────


def compute_anomaly(
    target: StyleFingerprint,
    corpus_fps: list[StyleFingerprint],
) -> AnomalyReport:
    """Compute anomaly score for *target* relative to *corpus_fps*.

    Uses per-feature z-scores and nearest-neighbor Euclidean distances.
    """
    if not corpus_fps:
        return AnomalyReport(work_id=target.work_id, anomaly_score=0.0)

    # Collect all feature keys present in the target
    feature_keys = sorted(target.features.keys())

    # Compute per-feature mean and std across corpus
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    for key in feature_keys:
        vals = [fp.features.get(key, 0.0) for fp in corpus_fps]
        n = len(vals)
        mean = sum(vals) / n
        variance = sum((v - mean) ** 2 for v in vals) / n
        means[key] = mean
        stds[key] = math.sqrt(variance)

    # Z-scores for target
    z_scores: dict[str, float] = {}
    for key in feature_keys:
        std = stds[key]
        if std > 0:
            z_scores[key] = (target.features[key] - means[key]) / std
        else:
            z_scores[key] = 0.0

    # Anomaly score = mean |z|
    anomaly_score = sum(abs(z) for z in z_scores.values()) / max(len(z_scores), 1)

    # Outlier features: |z| > 2.0
    outlier_features: list[FeatureDiff] = []
    for key in sorted(z_scores, key=lambda k: abs(z_scores[k]), reverse=True):
        if abs(z_scores[key]) > 2.0:
            outlier_features.append(
                FeatureDiff(
                    name=key,
                    left_value=target.features[key],
                    right_value=means[key],
                    difference=z_scores[key],
                )
            )

    # Nearest neighbors by Euclidean distance
    distances: list[tuple[str, float]] = []
    for fp in corpus_fps:
        common = sorted(set(target.features) & set(fp.features))
        dist = math.sqrt(
            sum((target.features[k] - fp.features.get(k, 0.0)) ** 2 for k in common)
        )
        distances.append((fp.work_id, round(dist, 6)))
    distances.sort(key=lambda x: x[1])
    nearest = distances[:5]

    return AnomalyReport(
        work_id=target.work_id,
        anomaly_score=round(anomaly_score, 6),
        outlier_features=outlier_features,
        nearest_neighbors=nearest,
    )


# ── Corpus loader ────────────────────────────────────────────────────────


def load_corpus_fingerprints(
    dataset: str = "dcml_bach_chorales",
    *,
    limit: int | None = None,
) -> list[StyleFingerprint]:
    """Load evidence bundles and compute fingerprints for a dataset.

    Parameters
    ----------
    dataset : str
        Dataset name under ``data/derived/``.
    limit : int, optional
        Maximum number of bundles to process.

    Returns
    -------
    list[StyleFingerprint]
    """
    derived_dir = Path("data/derived") / dataset
    if not derived_dir.exists():
        # Try relative to the package root
        pkg_root = Path(__file__).resolve().parent.parent.parent
        derived_dir = pkg_root / "data" / "derived" / dataset
    if not derived_dir.exists():
        return []

    bundle_files = sorted(derived_dir.glob("*.evidence_bundle.json"))
    if limit is not None:
        bundle_files = bundle_files[:limit]

    fingerprints: list[StyleFingerprint] = []
    for bf in bundle_files:
        try:
            with open(bf, encoding="utf-8") as f:
                data = json.load(f)
            fp = compute_style_fingerprint(data)
            fingerprints.append(fp)
        except (json.JSONDecodeError, KeyError):
            continue

    return fingerprints


# ── Convenience: load a single bundle by work_id or path ─────────────────


def _load_bundle(specifier: str, dataset: str = "dcml_bach_chorales") -> dict:
    """Load an evidence bundle by file path or work_id search."""
    path = Path(specifier)
    if path.exists() and path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # Search derived directory
    derived_dir = Path("data/derived") / dataset
    if not derived_dir.exists():
        pkg_root = Path(__file__).resolve().parent.parent.parent
        derived_dir = pkg_root / "data" / "derived" / dataset

    for bf in derived_dir.glob("*.evidence_bundle.json"):
        if specifier in bf.stem:
            with open(bf, encoding="utf-8") as f:
                return json.load(f)

    raise FileNotFoundError(f"No evidence bundle found for: {specifier}")
