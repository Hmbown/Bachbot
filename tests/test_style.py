"""Tests for style fingerprinting and anomaly detection."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from bachbot.analysis.style import (
    AnomalyReport,
    StyleComparison,
    StyleFingerprint,
    compare_fingerprints,
    compute_anomaly,
    compute_style_fingerprint,
    load_corpus_fingerprints,
)

# ── Fixtures ─────────────────────────────────────────────────────────────

_SAMPLE_BUNDLE: dict = {
    "work_id": "test_chorale_001",
    "metadata": {
        "key_tonic": "C",
        "key_mode": "major",
        "genre": "chorale",
        "encoding_id": "test_enc_001",
    },
    "passage_refs": [
        {"measure_start": i, "measure_end": i, "voice_ids": ["S", "A", "T", "B"]}
        for i in range(1, 17)
    ],
    "deterministic_findings": {
        "harmony": [
            {
                "roman_numeral_candidate_set": [label],
                "onset": float(i),
                "duration": 1.0,
                "local_key": "C major",
                "ref_id": f"test:m{i // 4 + 1}",
                "nonharmonic_tone_tags": [],
            }
            for i, label in enumerate(
                ["I", "IV", "V", "I", "ii", "V7", "I", "vi",
                 "IV", "V", "I", "iii", "V/V", "V", "I", "I"]
            )
        ],
        "cadences": [
            {"cadence_type": "PAC", "ref_id": "test:m4"},
            {"cadence_type": "HC", "ref_id": "test:m8"},
            {"cadence_type": "PAC", "ref_id": "test:m16"},
        ],
        "phrase_endings": [
            {"cadence_type": "PAC", "ref_id": "test:m4"},
        ],
        "voice_leading": {
            "contrary": 20,
            "similar": 10,
            "oblique": 5,
            "parallel": 8,
            "counterpoint": {"parallel_5ths": 1, "parallel_8ves": 0, "suspensions": 2},
            "spacing_issues": [],
            "range_issues": [{"type": "range_violation"}],
        },
        "modulation_graph": None,
        "distributions": {
            "pitch_class_histogram": {str(i): 10 + i for i in range(12)},
        },
    },
}

_DIFFERENT_BUNDLE: dict = {
    "work_id": "test_chorale_002",
    "metadata": {
        "key_tonic": "G",
        "key_mode": "minor",
        "genre": "chorale",
        "encoding_id": "test_enc_002",
    },
    "passage_refs": [
        {"measure_start": i, "measure_end": i, "voice_ids": ["S", "A", "T", "B"]}
        for i in range(1, 9)
    ],
    "deterministic_findings": {
        "harmony": [
            {
                "roman_numeral_candidate_set": [label],
                "onset": float(i),
                "duration": 1.0,
                "local_key": "G minor",
                "ref_id": f"test2:m{i // 4 + 1}",
                "nonharmonic_tone_tags": [],
            }
            for i, label in enumerate(
                ["i", "iv", "V", "i", "V7", "V/iv", "iv", "i"]
            )
        ],
        "cadences": [
            {"cadence_type": "PAC", "ref_id": "test2:m4"},
        ],
        "phrase_endings": [],
        "voice_leading": {
            "contrary": 5,
            "similar": 15,
            "oblique": 2,
            "parallel": 12,
            "counterpoint": {"parallel_5ths": 3, "parallel_8ves": 2, "suspensions": 0},
            "spacing_issues": [{"type": "spacing"}, {"type": "spacing"}],
            "range_issues": [],
        },
        "modulation_graph": None,
        "distributions": {},
    },
}


@pytest.fixture
def sample_bundle() -> dict:
    return _SAMPLE_BUNDLE


@pytest.fixture
def different_bundle() -> dict:
    return _DIFFERENT_BUNDLE


@pytest.fixture
def sample_fp(sample_bundle: dict) -> StyleFingerprint:
    return compute_style_fingerprint(sample_bundle)


@pytest.fixture
def different_fp(different_bundle: dict) -> StyleFingerprint:
    return compute_style_fingerprint(different_bundle)


# ── Tests ────────────────────────────────────────────────────────────────


class TestFeatureCount:
    """a) Fingerprint has >= 30 features."""

    def test_feature_count_minimum(self, sample_fp: StyleFingerprint) -> None:
        assert sample_fp.feature_count >= 30, (
            f"Expected >=30 features, got {sample_fp.feature_count}"
        )

    def test_feature_count_matches_dict(self, sample_fp: StyleFingerprint) -> None:
        assert sample_fp.feature_count == len(sample_fp.features)

    def test_all_values_are_float(self, sample_fp: StyleFingerprint) -> None:
        for k, v in sample_fp.features.items():
            assert isinstance(v, (int, float)), f"{k} is {type(v)}"


class TestSelfComparison:
    """b) compare(A, A) has cosine ~ 1.0, distance ~ 0.0."""

    def test_cosine_is_one(self, sample_fp: StyleFingerprint) -> None:
        result = compare_fingerprints(sample_fp, sample_fp)
        assert abs(result.cosine_similarity - 1.0) < 1e-4

    def test_distance_is_zero(self, sample_fp: StyleFingerprint) -> None:
        result = compare_fingerprints(sample_fp, sample_fp)
        assert result.euclidean_distance < 1e-6


class TestComparisonSymmetry:
    """c) compare(A, B).cosine == compare(B, A).cosine."""

    def test_cosine_symmetric(
        self, sample_fp: StyleFingerprint, different_fp: StyleFingerprint
    ) -> None:
        ab = compare_fingerprints(sample_fp, different_fp)
        ba = compare_fingerprints(different_fp, sample_fp)
        assert abs(ab.cosine_similarity - ba.cosine_similarity) < 1e-6

    def test_distance_symmetric(
        self, sample_fp: StyleFingerprint, different_fp: StyleFingerprint
    ) -> None:
        ab = compare_fingerprints(sample_fp, different_fp)
        ba = compare_fingerprints(different_fp, sample_fp)
        assert abs(ab.euclidean_distance - ba.euclidean_distance) < 1e-6


class TestDifferentFingerprints:
    """d) Known-different fingerprints produce detectable differences."""

    def test_cosine_less_than_one(
        self, sample_fp: StyleFingerprint, different_fp: StyleFingerprint
    ) -> None:
        result = compare_fingerprints(sample_fp, different_fp)
        assert result.cosine_similarity < 0.9999

    def test_distance_positive(
        self, sample_fp: StyleFingerprint, different_fp: StyleFingerprint
    ) -> None:
        result = compare_fingerprints(sample_fp, different_fp)
        assert result.euclidean_distance > 0.1

    def test_most_different_populated(
        self, sample_fp: StyleFingerprint, different_fp: StyleFingerprint
    ) -> None:
        result = compare_fingerprints(sample_fp, different_fp)
        assert len(result.most_different) > 0

    def test_most_similar_populated(
        self, sample_fp: StyleFingerprint, different_fp: StyleFingerprint
    ) -> None:
        result = compare_fingerprints(sample_fp, different_fp)
        assert len(result.most_similar) > 0

    def test_constructed_fingerprints_detect_differences(self) -> None:
        """Construct two fingerprints with known features and verify detection."""
        fp_a = StyleFingerprint(
            work_id="synth_a",
            feature_count=3,
            features={"x": 10.0, "y": 0.0, "z": 5.0},
        )
        fp_b = StyleFingerprint(
            work_id="synth_b",
            feature_count=3,
            features={"x": 0.0, "y": 10.0, "z": 5.0},
        )
        result = compare_fingerprints(fp_a, fp_b)
        assert result.cosine_similarity < 0.5
        assert result.euclidean_distance > 10.0
        # z should be in most_similar (difference=0)
        similar_names = {d.name for d in result.most_similar}
        assert "z" in similar_names


class TestAnomalyDetection:
    """e) Outlier gets the highest anomaly score."""

    def test_outlier_highest_score(self) -> None:
        # Corpus of similar fingerprints
        corpus = [
            StyleFingerprint(
                work_id=f"normal_{i}",
                feature_count=3,
                features={"a": 5.0 + i * 0.1, "b": 10.0 - i * 0.1, "c": 3.0},
            )
            for i in range(10)
        ]
        outlier = StyleFingerprint(
            work_id="outlier",
            feature_count=3,
            features={"a": 100.0, "b": -50.0, "c": 3.0},
        )
        normal = StyleFingerprint(
            work_id="normal_test",
            feature_count=3,
            features={"a": 5.5, "b": 9.5, "c": 3.0},
        )
        report_outlier = compute_anomaly(outlier, corpus)
        report_normal = compute_anomaly(normal, corpus)
        assert report_outlier.anomaly_score > report_normal.anomaly_score

    def test_outlier_features_detected(self) -> None:
        corpus = [
            StyleFingerprint(
                work_id=f"c_{i}",
                feature_count=2,
                features={"x": 5.0 + i * 0.01, "y": 5.0 + i * 0.01},
            )
            for i in range(20)
        ]
        outlier = StyleFingerprint(
            work_id="odd",
            feature_count=2,
            features={"x": 500.0, "y": 5.0},
        )
        report = compute_anomaly(outlier, corpus)
        outlier_names = {f.name for f in report.outlier_features}
        assert "x" in outlier_names

    def test_nearest_neighbors_returned(self) -> None:
        corpus = [
            StyleFingerprint(
                work_id=f"n_{i}",
                feature_count=1,
                features={"v": float(i)},
            )
            for i in range(10)
        ]
        target = StyleFingerprint(
            work_id="t",
            feature_count=1,
            features={"v": 3.0},
        )
        report = compute_anomaly(target, corpus)
        assert len(report.nearest_neighbors) == 5
        # Closest should be n_3 (distance 0)
        assert report.nearest_neighbors[0][0] == "n_3"

    def test_empty_corpus(self) -> None:
        target = StyleFingerprint(
            work_id="alone",
            feature_count=1,
            features={"v": 1.0},
        )
        report = compute_anomaly(target, [])
        assert report.anomaly_score == 0.0


# ── Corpus integration ───────────────────────────────────────────────────


_CORPUS_DIR = Path("data/derived/dcml_bach_chorales")
_has_corpus = _CORPUS_DIR.exists() and any(_CORPUS_DIR.glob("*.evidence_bundle.json"))


@pytest.mark.skipif(not _has_corpus, reason="No corpus data available")
class TestCorpusFingerprints:
    """f) Load real bundles and verify consistent feature sets."""

    def test_load_five_fingerprints(self) -> None:
        fps = load_corpus_fingerprints("dcml_bach_chorales", limit=5)
        assert len(fps) == 5

    def test_consistent_feature_keys(self) -> None:
        fps = load_corpus_fingerprints("dcml_bach_chorales", limit=5)
        key_sets = [set(fp.features.keys()) for fp in fps]
        # All should have the same feature keys
        for ks in key_sets[1:]:
            assert ks == key_sets[0], f"Inconsistent keys: {ks ^ key_sets[0]}"

    def test_all_have_minimum_features(self) -> None:
        fps = load_corpus_fingerprints("dcml_bach_chorales", limit=5)
        for fp in fps:
            assert fp.feature_count >= 30

    def test_cosine_between_corpus_chorales(self) -> None:
        fps = load_corpus_fingerprints("dcml_bach_chorales", limit=5)
        comp = compare_fingerprints(fps[0], fps[1])
        # Real chorales should be somewhat similar
        assert comp.cosine_similarity > 0.5

    def test_anomaly_on_real_corpus(self) -> None:
        fps = load_corpus_fingerprints("dcml_bach_chorales", limit=10)
        report = compute_anomaly(fps[0], fps[1:])
        assert report.anomaly_score >= 0.0
        assert len(report.nearest_neighbors) <= 5


# ── CLI test ─────────────────────────────────────────────────────────────


@pytest.mark.skipif(not _has_corpus, reason="No corpus data available")
class TestCLI:
    """g) CLI style comparison works with fixture bundle paths."""

    def test_style_command(self) -> None:
        from typer.testing import CliRunner

        from bachbot.cli.analyze import app

        runner = CliRunner()
        bundles = sorted(_CORPUS_DIR.glob("*.evidence_bundle.json"))[:2]
        result = runner.invoke(app, ["style", str(bundles[0]), str(bundles[1])])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "cosine_similarity" in data
        assert "euclidean_distance" in data

    def test_anomaly_command(self) -> None:
        from typer.testing import CliRunner

        from bachbot.cli.analyze import app

        runner = CliRunner()
        bundles = sorted(_CORPUS_DIR.glob("*.evidence_bundle.json"))[:1]
        result = runner.invoke(
            app, ["anomaly", str(bundles[0]), "--limit", "5"]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "anomaly_score" in data
        assert "nearest_neighbors" in data
