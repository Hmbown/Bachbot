"""Tests for bachbot.exports.features — ML feature extraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bachbot.encodings.event_graph import EventGraph
from bachbot.exports.features import (
    FEATURE_CATALOG,
    extract_features,
    extract_note_sequences,
    export_dataset_csv,
    export_dataset_json,
)

_CORPUS_NORM = Path("data/normalized/dcml_bach_chorales")
_CORPUS_DERIVED = Path("data/derived/dcml_bach_chorales")


def _first_corpus_pair() -> tuple[Path, Path] | None:
    """Return (event_graph_path, bundle_path) for the first available chorale."""
    for gp in sorted(_CORPUS_NORM.glob("*.event_graph.json")):
        stem = gp.name.replace(".event_graph.json", "")
        bp = _CORPUS_DERIVED / f"{stem}.evidence_bundle.json"
        if bp.exists():
            return gp, bp
    return None


def _corpus_pairs(n: int = 10) -> list[tuple[Path, Path]]:
    """Return up to *n* evenly-spaced (event_graph, bundle) pairs."""
    all_pairs = []
    for gp in sorted(_CORPUS_NORM.glob("*.event_graph.json")):
        stem = gp.name.replace(".event_graph.json", "")
        bp = _CORPUS_DERIVED / f"{stem}.evidence_bundle.json"
        if bp.exists():
            all_pairs.append((gp, bp))
    if not all_pairs:
        return []
    step = max(1, len(all_pairs) // n)
    return all_pairs[::step][:n]


# ── Unit tests with synthetic data ──────────────────────────────────────

def _minimal_bundle() -> dict:
    return {
        "work_id": "TEST-001",
        "metadata": {"key_tonic": "C", "key_mode": "major"},
        "passage_refs": [],
        "deterministic_findings": {
            "harmony": [
                {"roman_numeral_candidate_set": ["I"], "local_key": "C major"},
                {"roman_numeral_candidate_set": ["V"], "local_key": "C major"},
                {"roman_numeral_candidate_set": ["I"], "local_key": "C major"},
            ],
            "cadences": [{"cadence_type": "PAC"}],
            "phrase_endings": [{"type": "HC"}],
            "voice_leading": {
                "counterpoint": {"parallel_5ths": 0, "parallel_8ves": 0, "suspensions": 1, "issues": []},
                "contrary": 10,
                "similar": 5,
                "oblique": 3,
                "parallel": 2,
                "spacing_issues": [],
                "range_issues": [],
            },
            "distributions": {"pitch_class_histogram": {"0": 10, "7": 8, "4": 6}},
        },
    }


def test_feature_catalog_has_entries() -> None:
    assert len(FEATURE_CATALOG) > 50
    names = {name for name, _, _ in FEATURE_CATALOG}
    assert "work_id" in names
    assert "chord_variety" in names
    assert "pitch_class_entropy" in names


def test_extract_features_minimal_bundle_no_graph() -> None:
    bundle = _minimal_bundle()
    features = extract_features(bundle)
    assert features["work_id"] == "TEST-001"
    assert features["key_tonic_pc"] == 0  # C
    assert features["key_mode"] == 0  # major
    assert features["harmonic_event_count"] == 3
    assert features["chord_variety"] == 2  # I and V
    assert features["cadence_count"] == 2  # 1 cadence + 1 phrase ending
    assert features["cadence_PAC"] == 1
    assert features["cadence_HC"] == 1
    assert features["contrary_motion"] == 10
    assert features["suspension_count"] == 1
    # Without graph, note-level features are zero
    assert features["note_count"] == 0
    assert features["pitch_class_entropy"] == 0
    # But distribution data should be available
    assert features["pitch_class_0"] == 10
    assert features["pitch_class_7"] == 8


def test_extract_features_harmonic_ratios() -> None:
    bundle = _minimal_bundle()
    features = extract_features(bundle)
    # 2 I + 1 V = 3 total. tonic = 2/3, dominant = 1/3
    assert features["tonic_ratio"] == round(2 / 3, 4)
    assert features["dominant_ratio"] == round(1 / 3, 4)
    assert features["subdominant_ratio"] == 0.0


def test_extract_features_key_modes() -> None:
    bundle = _minimal_bundle()
    bundle["metadata"]["key_mode"] = "minor"
    bundle["metadata"]["key_tonic"] = "A"
    features = extract_features(bundle)
    assert features["key_mode"] == 1
    assert features["key_tonic_pc"] == 9  # A


def test_extract_features_all_catalog_keys_present() -> None:
    """Every feature in the catalog must be present in the output dict."""
    bundle = _minimal_bundle()
    features = extract_features(bundle)
    catalog_names = {name for name, _, _ in FEATURE_CATALOG}
    missing = catalog_names - set(features.keys())
    assert not missing, f"Missing features: {missing}"


def test_extract_features_voice_count_from_passage_refs() -> None:
    """voice_count must count distinct voices across all passage_refs."""
    bundle = _minimal_bundle()
    bundle["passage_refs"] = [
        {"voice_ids": ["S", "A", "T", "B"], "measure_number_logical": 1},
        {"voice_ids": ["S", "A", "T", "B"], "measure_number_logical": 2},
    ]
    features = extract_features(bundle)
    assert features["voice_count"] == 4
    assert features["measure_count"] == 2


def test_export_csv_roundtrip(tmp_path: Path) -> None:
    bundle = _minimal_bundle()
    rows = [extract_features(bundle)]
    out = tmp_path / "test.csv"
    export_dataset_csv(rows, out)
    assert out.exists()
    lines = out.read_text().splitlines()
    assert len(lines) == 2  # header + 1 row
    assert "work_id" in lines[0]


def test_export_json_roundtrip(tmp_path: Path) -> None:
    bundle = _minimal_bundle()
    rows = [extract_features(bundle)]
    out = tmp_path / "test.json"
    export_dataset_json(rows, out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data) == 1
    assert data[0]["work_id"] == "TEST-001"


# ── Corpus integration tests ───────────────────────────────────────────

@pytest.mark.skipif(not _first_corpus_pair(), reason="No corpus data available")
def test_extract_features_corpus_first_chorale() -> None:
    """Extract features from the first real corpus chorale with event graph."""
    gp, bp = _first_corpus_pair()
    graph = EventGraph.model_validate(json.loads(gp.read_text(encoding="utf-8")))
    bundle = json.loads(bp.read_text(encoding="utf-8"))
    features = extract_features(bundle, graph)

    # With graph, note-level features must be populated
    assert features["note_count"] > 0
    assert features["total_duration_quarters"] > 0
    assert features["onset_count"] > 0
    assert features["pitch_class_entropy"] > 0
    # Structural features must be correct
    assert features["voice_count"] == 4  # SATB chorales
    # At least some stepwise motion
    assert features["stepwise_soprano"] > 0
    # All catalog keys present
    catalog_names = {name for name, _, _ in FEATURE_CATALOG}
    missing = catalog_names - set(features.keys())
    assert not missing, f"Missing features: {missing}"


@pytest.mark.skipif(not _first_corpus_pair(), reason="No corpus data available")
def test_extract_note_sequences_corpus() -> None:
    gp, _ = _first_corpus_pair()
    graph = EventGraph.model_validate(json.loads(gp.read_text(encoding="utf-8")))
    seqs = extract_note_sequences(graph)

    for role in ("soprano", "alto", "tenor", "bass"):
        assert f"pitch_{role}" in seqs
        assert f"duration_{role}" in seqs
        assert f"onset_{role}" in seqs
        # Pitches should be MIDI ints in reasonable range
        pitches = seqs[f"pitch_{role}"]
        assert len(pitches) > 0
        assert all(30 < p < 100 for p in pitches)


@pytest.mark.parametrize(
    "pair",
    _corpus_pairs(10),
    ids=lambda p: p[0].stem[:40],
)
def test_extract_features_corpus_parametrized(pair: tuple[Path, Path]) -> None:
    """Parametrized: features extract cleanly across 10 evenly-spaced corpus chorales."""
    gp, bp = pair
    graph = EventGraph.model_validate(json.loads(gp.read_text(encoding="utf-8")))
    bundle = json.loads(bp.read_text(encoding="utf-8"))
    features = extract_features(bundle, graph)
    assert features["note_count"] > 0
    assert features["harmonic_event_count"] > 0
    assert len(features) >= len(FEATURE_CATALOG)
