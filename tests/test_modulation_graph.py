"""Tests for SHA-2820: Modulation graph with pivot chord detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bachbot.analysis.graphs.modulation_graph import (
    KeyRegion,
    ModulationEdge,
    ModulationGraph,
    _classify_modulation,
    _key_as_degree,
    _segment_regions,
    build_modulation_graph,
    build_modulation_graph_from_events,
    tonal_distance,
)
from bachbot.models.harmonic_event import HarmonicEvent


# ── Helpers ──


def _make_event(
    onset: float,
    measure: int,
    candidates: list[str],
    local_key: str = "C major",
    encoding_id: str = "test",
) -> HarmonicEvent:
    return HarmonicEvent(
        harmonic_event_id=f"{encoding_id}:h{measure}:{int(onset * 100)}",
        ref_id=f"{encoding_id}:m{measure}",
        onset=onset,
        duration=1.0,
        verticality_class="triad",
        local_key=local_key,
        global_key="C major",
        roman_numeral_candidate_set=candidates,
    )


# ── tonal_distance tests ──


def test_tonal_distance_same_key():
    assert tonal_distance("C major", "C major") == 0


def test_tonal_distance_relative_minor():
    """C major and A minor are relative keys → distance 0."""
    assert tonal_distance("C major", "A minor") == 0


def test_tonal_distance_dominant():
    """C major to G major → 1 step on circle of fifths."""
    assert tonal_distance("C major", "G major") == 1


def test_tonal_distance_subdominant():
    """C major to F major → 1 step (going the other direction)."""
    assert tonal_distance("C major", "F major") == 1


def test_tonal_distance_two_sharps():
    """C major to D major → 2 steps."""
    assert tonal_distance("C major", "D major") == 2


def test_tonal_distance_symmetric():
    """Distance is symmetric."""
    assert tonal_distance("C major", "Eb major") == tonal_distance("Eb major", "C major")


def test_tonal_distance_tritone():
    """C major to F# major → 6 steps (maximum)."""
    assert tonal_distance("C major", "F# major") == 6


def test_tonal_distance_minor_keys():
    """A minor to E minor → 1 step."""
    assert tonal_distance("A minor", "E minor") == 1


# ── _key_as_degree tests ──


def test_key_as_degree_tonic():
    assert _key_as_degree("C major", "C major") == "I"


def test_key_as_degree_dominant():
    assert _key_as_degree("G major", "C major") == "V"


def test_key_as_degree_vi():
    assert _key_as_degree("A minor", "C major") == "vi"


def test_key_as_degree_minor_context():
    """III in minor context → Eb in C minor."""
    assert _key_as_degree("Eb major", "C minor") == "III"


# ── _segment_regions tests ──


def test_segment_single_key():
    """All events in C major → one region."""
    events = [
        _make_event(0.0, 1, ["I"], "C major"),
        _make_event(1.0, 1, ["IV"], "C major"),
        _make_event(2.0, 1, ["V"], "C major"),
        _make_event(3.0, 2, ["I"], "C major"),
    ]
    regions = _segment_regions(events, "test", "C major")
    assert len(regions) == 1
    assert regions[0][0].key == "C major"
    assert regions[0][0].event_count == 4


def test_segment_two_regions():
    """C major → G major with enough events per region."""
    events = [
        _make_event(0.0, 1, ["I"], "C major"),
        _make_event(1.0, 1, ["IV"], "C major"),
        _make_event(2.0, 2, ["V"], "C major"),
        _make_event(3.0, 2, ["I"], "C major"),
        _make_event(4.0, 3, ["I"], "G major"),
        _make_event(5.0, 3, ["IV"], "G major"),
        _make_event(6.0, 4, ["V"], "G major"),
        _make_event(7.0, 4, ["I"], "G major"),
    ]
    regions = _segment_regions(events, "test", "C major")
    assert len(regions) == 2
    assert regions[0][0].key == "C major"
    assert regions[1][0].key == "G major"


def test_segment_merges_short_regions():
    """A very short deviation (< 3 events) gets merged into predecessor."""
    events = [
        _make_event(0.0, 1, ["I"], "C major"),
        _make_event(1.0, 1, ["IV"], "C major"),
        _make_event(2.0, 1, ["V"], "C major"),
        _make_event(3.0, 2, ["V"], "G major"),  # short deviation
        _make_event(4.0, 2, ["I"], "G major"),  # only 2 events
        _make_event(5.0, 3, ["I"], "C major"),
        _make_event(6.0, 3, ["IV"], "C major"),
        _make_event(7.0, 3, ["V"], "C major"),
    ]
    regions = _segment_regions(events, "test", "C major")
    # Short G major group (2 events) merged into C major
    assert len(regions) == 1
    assert regions[0][0].key == "C major"


def test_segment_preserves_long_deviation():
    """A longer deviation (>= 3 events) stays as a separate region."""
    events = [
        _make_event(0.0, 1, ["I"], "C major"),
        _make_event(1.0, 1, ["IV"], "C major"),
        _make_event(2.0, 1, ["V"], "C major"),
        _make_event(3.0, 2, ["I"], "G major"),
        _make_event(4.0, 2, ["IV"], "G major"),
        _make_event(5.0, 2, ["V"], "G major"),  # 3 events → kept
        _make_event(6.0, 3, ["I"], "C major"),
        _make_event(7.0, 3, ["IV"], "C major"),
        _make_event(8.0, 3, ["V"], "C major"),
    ]
    regions = _segment_regions(events, "test", "C major")
    assert len(regions) == 3
    assert regions[0][0].key == "C major"
    assert regions[1][0].key == "G major"
    assert regions[2][0].key == "C major"


# ── _classify_modulation tests ──


def test_classify_common_chord():
    """V chord is diatonic in both C major and G major → common_chord."""
    exit_event = _make_event(3.0, 2, ["V"], "C major")
    entry_event = _make_event(4.0, 3, ["I"], "G major")
    mod_type, pivot = _classify_modulation(exit_event, entry_event, "C major", "G major")
    assert mod_type == "common_chord"
    assert pivot == "V"


def test_classify_chromatic():
    """Secondary dominant at boundary → chromatic modulation."""
    exit_event = _make_event(3.0, 2, ["V/V"], "C major")
    entry_event = _make_event(4.0, 3, ["V"], "G major")
    mod_type, pivot = _classify_modulation(exit_event, entry_event, "C major", "G major")
    assert mod_type == "chromatic"
    assert pivot is None


def test_classify_direct():
    """No common chord and no secondary dominant → direct modulation."""
    exit_event = _make_event(3.0, 2, ["vi"], "C major")
    entry_event = _make_event(4.0, 3, ["I"], "Eb major")
    mod_type, pivot = _classify_modulation(exit_event, entry_event, "C major", "Eb major")
    assert mod_type == "direct"
    assert pivot is None


# ── build_modulation_graph_from_events tests ──


def test_build_from_events_tonic_dominant_tonic():
    """Classic I–V–I tonal plan."""
    events = (
        [_make_event(float(i), i + 1, ["I" if i % 2 == 0 else "IV"], "C major") for i in range(5)]
        + [_make_event(float(i + 5), i + 6, ["I" if i % 2 == 0 else "V"], "G major") for i in range(4)]
        + [_make_event(float(i + 9), i + 10, ["V" if i == 0 else "I"], "C major") for i in range(4)]
    )
    mg = build_modulation_graph_from_events(events, "test", "C major")

    assert isinstance(mg, ModulationGraph)
    assert len(mg.regions) == 3
    assert mg.regions[0].key == "C major"
    assert mg.regions[1].key == "G major"
    assert mg.regions[2].key == "C major"
    assert len(mg.edges) == 2
    assert mg.edges[0].from_key == "C major"
    assert mg.edges[0].to_key == "G major"
    assert mg.edges[0].tonal_distance == 1
    assert mg.edges[1].from_key == "G major"
    assert mg.edges[1].to_key == "C major"
    assert mg.tonal_plan == "I–V–I"


def test_build_from_events_single_key():
    """No modulation → one region, no edges, simple plan."""
    events = [_make_event(float(i), i + 1, ["I"], "C major") for i in range(8)]
    mg = build_modulation_graph_from_events(events, "test", "C major")

    assert len(mg.regions) == 1
    assert len(mg.edges) == 0
    assert mg.tonal_plan == "I"


def test_build_from_events_minor():
    """Minor key tonal plan: i–III–i."""
    events = (
        [_make_event(float(i), i + 1, ["i"], "A minor") for i in range(4)]
        + [_make_event(float(i + 4), i + 5, ["I"], "C major") for i in range(4)]
        + [_make_event(float(i + 8), i + 9, ["i"], "A minor") for i in range(4)]
    )
    mg = build_modulation_graph_from_events(events, "test", "A minor")

    assert len(mg.regions) == 3
    assert mg.tonal_plan == "i–III–i"
    assert mg.edges[0].tonal_distance == 0  # relative keys


def test_modulation_edge_has_correct_measure():
    """Edge measure should be the start of the new region."""
    events = (
        [_make_event(float(i), i + 1, ["I"], "C major") for i in range(4)]
        + [_make_event(float(i + 4), i + 5, ["I"], "G major") for i in range(4)]
    )
    mg = build_modulation_graph_from_events(events, "test", "C major")
    assert mg.edges[0].measure == 5  # G major region starts at measure 5


def test_region_measure_spans():
    """Regions should have correct measure start/end."""
    events = (
        [_make_event(float(i), i + 1, ["I"], "C major") for i in range(4)]
        + [_make_event(float(i + 4), i + 5, ["I"], "G major") for i in range(4)]
    )
    mg = build_modulation_graph_from_events(events, "test", "C major")
    assert mg.regions[0].measure_start == 1
    assert mg.regions[0].measure_end == 4
    assert mg.regions[1].measure_start == 5
    assert mg.regions[1].measure_end == 8


# ── Integration with EventGraph ──


def test_build_modulation_graph_from_graph(simple_chorale_graph):
    """build_modulation_graph should work on a real EventGraph without crashing."""
    mg = build_modulation_graph(simple_chorale_graph)
    assert isinstance(mg, ModulationGraph)
    assert len(mg.regions) >= 1
    assert mg.global_key != ""
    assert mg.tonal_plan != ""


def test_analysis_report_includes_modulation_graph(simple_chorale_graph):
    """analyze_chorale() should include modulation_graph in the report."""
    from bachbot.analysis.pipeline import analyze_chorale

    report = analyze_chorale(simple_chorale_graph)
    assert "regions" in report.modulation_graph
    assert "edges" in report.modulation_graph
    assert "tonal_plan" in report.modulation_graph


def test_evidence_bundle_includes_modulation_graph(simple_chorale_graph):
    """Evidence bundle should include modulation_graph in deterministic_findings."""
    from bachbot.analysis.pipeline import analyze_chorale
    from bachbot.claims.bundle import build_evidence_bundle

    report = analyze_chorale(simple_chorale_graph)
    bundle = build_evidence_bundle(simple_chorale_graph, report)
    findings = bundle.deterministic_findings
    assert "modulation_graph" in findings
    mg = findings["modulation_graph"]
    assert "regions" in mg
    assert "tonal_plan" in mg


# ── Corpus integration: modulation graph on real chorales ──

_CORPUS_DIR = Path("data/derived/dcml_bach_chorales")


def _sample_bundles(n: int = 10) -> list[Path]:
    files = sorted(_CORPUS_DIR.glob("*.evidence_bundle.json"))
    if not files:
        return []
    step = max(1, len(files) // n)
    return files[::step][:n]


@pytest.mark.parametrize("bundle_path", _sample_bundles(), ids=lambda p: p.stem[:40])
def test_modulation_graph_from_corpus_bundle(bundle_path: Path) -> None:
    """Build modulation graph from corpus evidence bundles — should not crash."""
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    harmony = data.get("deterministic_findings", {}).get("harmony", [])
    global_key = data.get("metadata", {}).get("key", "C major") or "C major"
    encoding_id = data.get("metadata", {}).get("encoding_id", "corpus")

    events = [HarmonicEvent.model_validate(h) for h in harmony]
    mg = build_modulation_graph_from_events(events, encoding_id, global_key)

    assert isinstance(mg, ModulationGraph)
    assert len(mg.regions) >= 1
    assert mg.tonal_plan != ""

    # Sanity: all edges reference valid region keys
    region_keys = {r.key for r in mg.regions}
    for edge in mg.edges:
        assert edge.from_key in region_keys
        assert edge.to_key in region_keys
        assert 0 <= edge.tonal_distance <= 6


@pytest.mark.parametrize("bundle_path", _sample_bundles(5), ids=lambda p: p.stem[:40])
def test_corpus_tonal_plan_starts_with_tonic(bundle_path: Path) -> None:
    """First region should be in the global key (or relative) for most chorales."""
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    harmony = data.get("deterministic_findings", {}).get("harmony", [])
    global_key = data.get("metadata", {}).get("key", "C major") or "C major"
    encoding_id = data.get("metadata", {}).get("encoding_id", "corpus")

    events = [HarmonicEvent.model_validate(h) for h in harmony]
    mg = build_modulation_graph_from_events(events, encoding_id, global_key)

    if mg.regions:
        first_region = mg.regions[0]
        dist = tonal_distance(first_region.key, global_key)
        assert dist <= 1, (
            f"First region {first_region.key} is {dist} steps from global key {global_key}"
        )
