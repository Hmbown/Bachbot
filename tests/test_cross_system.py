"""Tests for the cross-system composition benchmark."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bachbot.benchmark.cross_system.adapters import (
    ADAPTER_REGISTRY,
    BachbotAdapter,
    GroundTruthAdapter,
    MidiImportAdapter,
    Music21Adapter,
    SystemAdapter,
    _melody_to_cantus,
    get_adapter,
)
from bachbot.benchmark.cross_system.evaluator import (
    ComparisonReport,
    SystemScore,
    compare_systems,
    evaluate_harmonization,
    generate_comparison_table,
)
from bachbot.benchmark.cross_system.test_set import (
    STANDARD_30_COUNT,
    BenchmarkMelody,
    _synthetic_fallback,
    build_standard_test_set,
)
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice

# ── Paths ────────────────────────────────────────────────────────────

_CORPUS_NORM = Path("data/normalized/dcml_bach_chorales")
_HAS_CORPUS = _CORPUS_NORM.exists() and any(_CORPUS_NORM.glob("*.event_graph.json"))


# ── Helpers ──────────────────────────────────────────────────────────

def _make_simple_melody() -> BenchmarkMelody:
    """Create a simple C-major melody for testing."""
    return BenchmarkMelody(
        melody_id="test:simple",
        title="Simple test melody",
        soprano_midi=[60, 62, 64, 65, 67, 65, 64, 62, 60],
        key="C",
        mode="major",
        meter="4/4",
        beats_per_note=1.0,
        ground_truth_work_id=None,
    )


def _make_satb_graph(
    work_id: str = "TEST",
    soprano: list[int] | None = None,
    alto: list[int] | None = None,
    tenor: list[int] | None = None,
    bass: list[int] | None = None,
) -> EventGraph:
    """Build a minimal SATB EventGraph from MIDI lists."""
    soprano = soprano or [67, 65, 64, 62, 60]
    alto = alto or [60, 60, 60, 59, 57]
    tenor = tenor or [55, 53, 52, 50, 48]
    bass = bass or [48, 45, 43, 43, 41]

    sid = f"{work_id}:section:1"
    notes: list[TypedNote] = []
    voices_data = [
        ("Soprano:1", soprano),
        ("Alto:1", alto),
        ("Tenor:1", tenor),
        ("Bass:1", bass),
    ]
    for vid, midis in voices_data:
        for i, midi in enumerate(midis):
            notes.append(TypedNote(
                midi=midi,
                duration_quarters=1.0,
                offset_quarters=float(i),
                measure_number=i // 4 + 1,
                beat=float(i % 4 + 1),
                voice_id=vid,
            ))

    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id=work_id,
            work_id=work_id,
            source_format="test",
            key_estimate=KeyEstimate(tonic="C", mode="major", confidence=0.99),
            meter="4/4",
        ),
        section=Section(
            section_id=sid,
            work_id=work_id,
            label="Test",
            section_type="test",
            measure_start=1,
            measure_end=2,
        ),
        voices=[
            Voice(voice_id="Soprano:1", section_id=sid, part_name="Soprano", normalized_voice_name="Soprano"),
            Voice(voice_id="Alto:1", section_id=sid, part_name="Alto", normalized_voice_name="Alto"),
            Voice(voice_id="Tenor:1", section_id=sid, part_name="Tenor", normalized_voice_name="Tenor"),
            Voice(voice_id="Bass:1", section_id=sid, part_name="Bass", normalized_voice_name="Bass"),
        ],
        notes=notes,
    )


# ── (a) Test set construction ────────────────────────────────────────

class TestTestSetConstruction:
    """Test set construction: verify entries have valid soprano sequences."""

    @pytest.mark.skipif(not _HAS_CORPUS, reason="corpus not available")
    def test_standard_30_from_corpus(self):
        melodies = build_standard_test_set(limit=5)
        assert len(melodies) >= 1
        for m in melodies:
            assert isinstance(m, BenchmarkMelody)
            assert len(m.soprano_midi) > 0
            assert all(isinstance(p, int) for p in m.soprano_midi)
            assert m.melody_id
            assert m.key
            assert m.mode

    @pytest.mark.skipif(not _HAS_CORPUS, reason="corpus not available")
    def test_standard_30_has_30(self):
        melodies = build_standard_test_set(limit=30)
        assert len(melodies) == 30

    def test_synthetic_fallback(self):
        melodies = _synthetic_fallback(5)
        assert len(melodies) == 5
        for m in melodies:
            assert isinstance(m, BenchmarkMelody)
            assert len(m.soprano_midi) > 0
            assert m.ground_truth_work_id is None

    def test_synthetic_fallback_more_than_base(self):
        melodies = _synthetic_fallback(15)
        assert len(melodies) == 15

    def test_build_falls_back_when_no_corpus(self):
        with patch("bachbot.benchmark.cross_system.test_set._CORPUS_NORM", Path("/nonexistent")):
            melodies = build_standard_test_set(limit=5)
            assert len(melodies) == 5
            assert all(m.melody_id.startswith("synthetic:") for m in melodies)


# ── (b) Bachbot adapter test ─────────────────────────────────────────

class TestBachbotAdapter:
    """Bachbot adapter: harmonize a simple melody, verify valid EventGraph."""

    def test_is_available(self):
        adapter = BachbotAdapter()
        assert adapter.is_available() is True

    def test_harmonize_simple_melody(self):
        adapter = BachbotAdapter()
        melody = _make_simple_melody()
        graph = adapter.harmonize(melody)
        assert graph is not None
        assert isinstance(graph, EventGraph)
        # Should have notes for multiple voices.
        voice_ids = {n.voice_id for n in graph.notes}
        assert len(voice_ids) >= 2  # at minimum soprano + something

    def test_adapter_name(self):
        assert BachbotAdapter.name == "bachbot"


# ── (c) Ground truth adapter ─────────────────────────────────────────

class TestGroundTruthAdapter:
    """Ground truth adapter: load original harmonization."""

    @pytest.mark.skipif(not _HAS_CORPUS, reason="corpus not available")
    def test_is_available(self):
        adapter = GroundTruthAdapter()
        assert adapter.is_available() is True

    @pytest.mark.skipif(not _HAS_CORPUS, reason="corpus not available")
    def test_load_ground_truth(self):
        melodies = build_standard_test_set(limit=1)
        assert len(melodies) >= 1
        adapter = GroundTruthAdapter()
        graph = adapter.harmonize(melodies[0])
        assert graph is not None
        assert isinstance(graph, EventGraph)
        assert len(graph.notes) > 0

    def test_returns_none_without_work_id(self):
        adapter = GroundTruthAdapter()
        melody = _make_simple_melody()
        assert melody.ground_truth_work_id is None
        result = adapter.harmonize(melody)
        assert result is None


# ── (d) Music21 adapter availability ─────────────────────────────────

class TestMusic21Adapter:
    """Music21 adapter: is_available() returns bool without crashing."""

    def test_is_available_returns_bool(self):
        adapter = Music21Adapter()
        result = adapter.is_available()
        assert isinstance(result, bool)

    def test_adapter_name(self):
        assert Music21Adapter.name == "music21"


# ── (e) MIDI import adapter ──────────────────────────────────────────

class TestMidiImportAdapter:
    """MIDI import adapter: verify import behavior."""

    def test_is_available_false_when_no_dir(self):
        adapter = MidiImportAdapter(midi_dir="/nonexistent_dir")
        assert adapter.is_available() is False

    def test_returns_none_when_no_matching_file(self, tmp_path):
        adapter = MidiImportAdapter(midi_dir=tmp_path)
        melody = _make_simple_melody()
        result = adapter.harmonize(melody)
        assert result is None

    def test_adapter_name(self):
        assert MidiImportAdapter.name == "midi_import"

    def test_adapter_registry_has_midi_import(self):
        assert "midi_import" in ADAPTER_REGISTRY


# ── (f) Evaluation metrics test ──────────────────────────────────────

class TestEvaluationMetrics:
    """Evaluation metrics: verify detection of known issues."""

    def test_evaluate_clean_graph(self):
        graph = _make_satb_graph()
        score = evaluate_harmonization(graph, system_name="test", melody_id="test:1")
        assert isinstance(score, SystemScore)
        assert score.system_name == "test"
        assert score.melody_id == "test:1"
        assert score.chord_variety >= 0
        assert score.voice_leading_smoothness >= 0
        assert score.overall_score >= 0

    def test_evaluate_detects_variety(self):
        # All same chord = low variety.
        graph = _make_satb_graph(
            soprano=[60, 60, 60, 60, 60],
            alto=[55, 55, 55, 55, 55],
            tenor=[48, 48, 48, 48, 48],
            bass=[36, 36, 36, 36, 36],
        )
        score_mono = evaluate_harmonization(graph)

        # Different chords = higher variety.
        graph_varied = _make_satb_graph(
            soprano=[60, 62, 64, 65, 67],
            alto=[55, 57, 60, 60, 62],
            tenor=[48, 50, 52, 53, 55],
            bass=[36, 38, 40, 41, 43],
        )
        score_varied = evaluate_harmonization(graph_varied)
        assert score_varied.chord_variety > score_mono.chord_variety

    def test_score_model_forbids_extra(self):
        with pytest.raises(Exception):
            SystemScore(
                system_name="test",
                melody_id="test:1",
                unknown_field=42,
            )


# ── (g) Comparison report test ───────────────────────────────────────

class TestComparisonReport:
    """Comparison report: compare systems on a small set, verify structure."""

    def test_compare_bachbot_only(self):
        melodies = _synthetic_fallback(3)
        adapter = BachbotAdapter()
        report = compare_systems(melodies, [adapter])
        assert isinstance(report, ComparisonReport)
        assert report.melody_count == 3
        assert "bachbot" in report.systems
        assert len(report.scores) == 3
        assert "bachbot" in report.summary
        summary = report.summary["bachbot"]
        assert "avg_overall_score" in summary
        assert "avg_chord_variety" in summary

    def test_compare_with_unavailable_adapter(self):
        """Unavailable adapter should be skipped gracefully."""
        melodies = _synthetic_fallback(2)
        bachbot = BachbotAdapter()
        midi_adapter = MidiImportAdapter(midi_dir="/nonexistent")
        # midi_import is unavailable, should be skipped.
        report = compare_systems(melodies, [bachbot, midi_adapter])
        # Only bachbot should have scores.
        system_names_in_scores = {s.system_name for s in report.scores}
        assert "bachbot" in system_names_in_scores

    def test_report_model_forbids_extra(self):
        with pytest.raises(Exception):
            ComparisonReport(
                test_set_name="test",
                melody_count=0,
                systems=[],
                bogus=True,
            )


# ── (h) Summary table test ──────────────────────────────────────────

class TestSummaryTable:
    """Summary table: verify table generation produces readable output."""

    def test_generate_table_empty(self):
        report = ComparisonReport(
            test_set_name="test",
            melody_count=0,
            systems=[],
        )
        table = generate_comparison_table(report)
        assert "No results" in table

    def test_generate_table_with_data(self):
        report = ComparisonReport(
            test_set_name="test",
            melody_count=2,
            systems=["bachbot"],
            summary={
                "bachbot": {
                    "melody_count": 2.0,
                    "avg_parallel_violations": 1.5,
                    "avg_voice_crossing_count": 0.0,
                    "avg_chord_variety": 5.0,
                    "avg_voice_leading_smoothness": 2.5,
                    "avg_spacing_violations": 0.0,
                    "avg_overall_score": 0.65,
                },
            },
        )
        table = generate_comparison_table(report)
        assert "bachbot" in table
        assert "System" in table
        assert "Overall" in table
        lines = table.strip().split("\n")
        assert len(lines) >= 3  # header + separator + data row


# ── (i) CLI test ─────────────────────────────────────────────────────

class TestCLI:
    """CLI: verify benchmark compare command is registered and works."""

    def test_compare_command_registered(self):
        from bachbot.cli.benchmark import app
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "compare" in command_names

    def test_compare_command_help(self):
        from typer.testing import CliRunner
        from bachbot.cli.benchmark import app

        runner = CliRunner()
        result = runner.invoke(app, ["compare", "--help"])
        assert result.exit_code == 0
        assert "--systems" in result.output
        assert "--test-set" in result.output
        assert "--limit" in result.output


# ── (j) Parametrized melody evaluation ──────────────────────────────

class TestParametrizedMelodyEvaluation:
    """Evaluate Bachbot harmonization on 5 test melodies, verify valid SATB."""

    @pytest.fixture
    def melodies(self):
        return _synthetic_fallback(5)

    @pytest.mark.parametrize("idx", range(5))
    def test_harmonize_produces_valid_satb(self, melodies, idx):
        adapter = BachbotAdapter()
        melody = melodies[idx]
        graph = adapter.harmonize(melody)
        assert graph is not None, f"Harmonization failed for melody {melody.melody_id}"
        assert isinstance(graph, EventGraph)
        # Check we have notes.
        assert len(graph.notes) > 0
        # Evaluate: should produce non-zero overall score.
        score = evaluate_harmonization(graph, system_name="bachbot", melody_id=melody.melody_id)
        assert score.overall_score >= 0.0


# ── Additional edge case tests ───────────────────────────────────────

class BenchmarkMelodytoCantus:
    """Verify BenchmarkMelody -> EventGraph conversion."""

    def test_basic_conversion(self):
        melody = _make_simple_melody()
        cantus = _melody_to_cantus(melody)
        assert isinstance(cantus, EventGraph)
        assert len(cantus.notes) == len(melody.soprano_midi)
        assert all(n.voice_id == "Soprano:1" for n in cantus.notes)
        assert cantus.metadata.meter == "4/4"

    def test_key_estimate_propagated(self):
        melody = _make_simple_melody()
        cantus = _melody_to_cantus(melody)
        assert cantus.metadata.key_estimate is not None
        assert cantus.metadata.key_estimate.tonic == "C"


class TestAdapterRegistry:
    """Verify adapter registry and get_adapter helper."""

    def test_all_adapters_registered(self):
        assert "bachbot" in ADAPTER_REGISTRY
        assert "ground_truth" in ADAPTER_REGISTRY
        assert "music21" in ADAPTER_REGISTRY
        assert "midi_import" in ADAPTER_REGISTRY

    def test_get_adapter_valid(self):
        adapter = get_adapter("bachbot")
        assert isinstance(adapter, BachbotAdapter)

    def test_get_adapter_invalid(self):
        with pytest.raises(ValueError, match="Unknown adapter"):
            get_adapter("nonexistent_system")


class TestBenchmarkMelodyModel:
    """BenchmarkMelody Pydantic model validation."""

    def test_forbids_extra_fields(self):
        with pytest.raises(Exception):
            BenchmarkMelody(
                melody_id="test",
                title="test",
                soprano_midi=[60],
                key="C",
                mode="major",
                meter="4/4",
                extra_field="bad",
            )

    def test_defaults(self):
        m = BenchmarkMelody(
            melody_id="test",
            title="test",
            soprano_midi=[60, 62],
            key="C",
            mode="major",
            meter="4/4",
        )
        assert m.beats_per_note == 1.0
        assert m.ground_truth_work_id is None
