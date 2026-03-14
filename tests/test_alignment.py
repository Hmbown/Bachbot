from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bachbot.cli.main import app
from bachbot.encodings.alignment import align_editions
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.edition import VariantType
from bachbot.models.section import Section
from bachbot.models.voice import Voice


_CORPUS_DIR = Path("/Volumes/VIXinSSD/bachbot/data/normalized/dcml_bach_chorales")

_CORPUS_CHORALES = [
    "notes__001 Aus meines Herzens Grunde",
    "notes__002 Ich danke dir, lieber Herre",
    "notes__003 Ach Gott, vom Himmel sieh darein",
    "notes__004 Es ist das Heil uns kommen her",
    "notes__005 An Wasserflüssen Babylon",
]


def _voice(voice_id: str) -> Voice:
    return Voice(
        voice_id=voice_id,
        section_id="section_1",
        part_name=voice_id,
        normalized_voice_name=voice_id,
        instrument_or_role=voice_id,
    )


def _note(
    voice_id: str,
    midi: int | None,
    onset: float,
    duration: float,
    *,
    measure: int | None = None,
    beat: float | None = None,
    pitch: str | None = None,
    accidental: str | None = None,
    lyric: str | None = None,
    tie_start: bool = False,
    tie_stop: bool = False,
    is_rest: bool = False,
) -> TypedNote:
    inferred_measure = measure if measure is not None else int(onset // 4) + 1
    inferred_beat = beat if beat is not None else (onset % 4) + 1
    return TypedNote(
        pitch=pitch or (None if midi is None else f"midi-{midi}"),
        midi=midi,
        duration_quarters=duration,
        offset_quarters=onset,
        measure_number=inferred_measure,
        beat=inferred_beat,
        voice_id=voice_id,
        part_name=voice_id,
        accidental=accidental,
        lyric=lyric,
        tie_start=tie_start,
        tie_stop=tie_stop,
        is_rest=is_rest,
        source_ref=f"section_1:m{inferred_measure}:{voice_id}:{onset}",
    )


def _graph(notes: list[TypedNote], *, work_id: str = "SYNTH") -> EventGraph:
    measure_end = max(note.measure_number for note in notes) if notes else 1
    voice_ids = sorted({note.voice_id for note in notes})
    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id=f"{work_id.lower()}-encoding",
            work_id=work_id,
            title=f"{work_id} synthetic",
            source_format="test",
            key_estimate=KeyEstimate(tonic="C", mode="major", confidence=0.99),
        ),
        section=Section(
            section_id="section_1",
            work_id=work_id,
            label=f"{work_id} section",
            section_type="movement",
            measure_start=1,
            measure_end=measure_end,
        ),
        voices=[_voice(voice_id) for voice_id in voice_ids],
        notes=notes,
    )


def test_align_editions_classifies_same_address_variants() -> None:
    left = _graph(
        [
            _note("S", 60, 0.0, 1.0, pitch="C4", accidental=None, lyric="Kyrie"),
            _note("A", 55, 0.0, 1.0, pitch="G3"),
        ]
    )
    right = _graph(
        [
            _note("S", 62, 0.0, 2.0, pitch="D4", accidental="#", lyric="Christe", tie_start=True),
            _note("A", 55, 0.0, 1.0, pitch="G3"),
        ]
    )

    report = align_editions(left, right, left_label="riemen", right_label="nba")

    assert report.left_label == "riemen"
    assert report.right_label == "nba"
    assert report.summary.unchanged_count == 1
    assert report.summary.by_type == {
        "accidental": 1,
        "pitch": 1,
        "rhythm": 1,
        "text": 1,
        "tie": 1,
    }
    assert report.summary.by_voice == {"S": 5}
    assert report.summary.by_measure == {1: 5}
    assert report.voice_span_comparison == {"A": (1, 1), "S": (1, 1)}
    assert {variant.variant_type for variant in report.variants} == {
        VariantType.PITCH,
        VariantType.RHYTHM,
        VariantType.ACCIDENTAL,
        VariantType.TEXT,
        VariantType.TIE,
    }


@pytest.mark.parametrize(
    ("left_notes", "right_notes", "expected_by_type"),
    [
        (
            [_note("S", 60, 0.0, 1.0, pitch="C4")],
            [_note("S", 62, 0.0, 1.0, pitch="D4")],
            {"pitch": 1},
        ),
        (
            [_note("S", 60, 0.0, 1.0, pitch="C4")],
            [_note("S", 60, 0.0, 2.0, pitch="C4")],
            {"rhythm": 1},
        ),
        (
            [_note("S", 61, 0.0, 1.0, pitch="C#4", accidental="#")],
            [_note("S", 61, 0.0, 1.0, pitch="C#4", accidental=None)],
            {"accidental": 1},
        ),
        (
            [_note("S", 60, 0.0, 1.0, pitch="C4", lyric="Kyrie")],
            [_note("S", 60, 0.0, 1.0, pitch="C4", lyric="Christe")],
            {"text": 1},
        ),
        (
            [
                _note("S", 60, 0.0, 1.0, pitch="C4"),
                _note("S", 62, 1.0, 1.0, pitch="D4"),
            ],
            [
                _note("S", 59, 0.0, 1.0, pitch="B3"),
                _note("S", 60, 1.0, 1.0, pitch="C4"),
                _note("S", 62, 2.0, 1.0, pitch="D4"),
            ],
            {"added_note": 1, "rhythm": 2},
        ),
    ],
    ids=["pitch", "duration", "accidental", "text", "shifted-sequence"],
)
def test_align_editions_reports_expected_variant_groups(
    left_notes: list[TypedNote],
    right_notes: list[TypedNote],
    expected_by_type: dict[str, int],
) -> None:
    report = align_editions(_graph(left_notes), _graph(right_notes))

    assert report.summary.by_type == expected_by_type
    assert report.summary.by_voice == {"S": sum(expected_by_type.values())}
    assert report.summary.by_measure == {1: sum(expected_by_type.values())}
    assert report.voice_span_comparison["S"] == (len(left_notes), len(right_notes))


def test_align_editions_tracks_added_and_removed_notes_and_keeps_voices_distinct() -> None:
    left = _graph(
        [
            _note("S", 60, 0.0, 1.0, pitch="C4"),
            _note("A", 64, 0.0, 1.0, pitch="E4"),
            _note("T", 55, 1.0, 1.0, pitch="G3"),
        ]
    )
    right = _graph(
        [
            _note("S", 60, 0.0, 1.0, pitch="C4"),
            _note("A", 65, 0.0, 1.0, pitch="F4"),
            _note("B", 48, 1.0, 1.0, pitch="C3"),
        ]
    )

    report = align_editions(left, right)

    assert report.summary.by_type["pitch"] == 1
    assert report.summary.by_type["removed_note"] == 1
    assert report.summary.by_type["added_note"] == 1
    assert report.summary.by_voice == {"A": 1, "B": 1, "T": 1}
    assert report.summary.by_measure == {1: 3}
    pitch_variant = next(item for item in report.variants if item.variant_type == VariantType.PITCH)
    assert pitch_variant.address.voice_id == "A"
    assert pitch_variant.left_note is not None and pitch_variant.right_note is not None
    removed_variant = next(item for item in report.variants if item.variant_type == VariantType.REMOVED_NOTE)
    added_variant = next(item for item in report.variants if item.variant_type == VariantType.ADDED_NOTE)
    assert removed_variant.address.voice_id == "T"
    assert added_variant.address.voice_id == "B"


def test_corpus_diff_cli_outputs_variant_report(fixture_dir: Path, tmp_path: Path) -> None:
    left_path = fixture_dir / "chorales" / "simple_chorale.musicxml"
    right_path = tmp_path / "simple_chorale_variant.musicxml"
    tree = ET.parse(left_path)
    root = tree.getroot()
    first_step = root.find(".//note/pitch/step")
    assert first_step is not None
    first_step.text = "D" if first_step.text != "D" else "E"
    tree.write(right_path, encoding="utf-8", xml_declaration=True)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "corpus",
            "diff",
            str(left_path),
            str(right_path),
            "--edition-a",
            "riemen",
            "--edition-b",
            "nba",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["left_label"] == "riemen"
    assert payload["right_label"] == "nba"
    assert payload["summary"]["by_type"]["pitch"] == 1
    assert payload["variants"][0]["address"]["voice_id"] == "S"


@pytest.mark.skipif(not _CORPUS_DIR.exists(), reason="Corpus not available")
@pytest.mark.parametrize(
    "chorale_stem",
    _CORPUS_CHORALES,
    ids=[s.split("__")[1][:20] for s in _CORPUS_CHORALES],
)
def test_align_editions_detects_simulated_editorial_variants_on_real_chorales(
    chorale_stem: str,
) -> None:
    """Load a real chorale, simulate editorial differences, verify detection."""
    graph_path = _CORPUS_DIR / f"{chorale_stem}.event_graph.json"
    if not graph_path.exists():
        pytest.skip(f"Missing: {graph_path.name}")

    original = EventGraph.model_validate_json(graph_path.read_text(encoding="utf-8"))

    # Create modified edition with known editorial changes
    modified_notes: list[TypedNote] = []
    pitch_changed = False
    rhythm_changed = False

    for note in original.notes:
        new_note = note.model_copy()
        # Change pitch of first soprano note
        if (
            not pitch_changed
            and note.voice_id == "S"
            and note.midi is not None
            and not note.is_rest
        ):
            new_note = note.model_copy(
                update={"midi": note.midi + 2, "pitch": f"edit-{note.pitch}"}
            )
            pitch_changed = True
        # Change duration of first alto note
        elif (
            not rhythm_changed
            and note.voice_id == "A"
            and not note.is_rest
        ):
            new_note = note.model_copy(
                update={"duration_quarters": note.duration_quarters * 2}
            )
            rhythm_changed = True
        else:
            pass
        modified_notes.append(new_note)

    modified = original.model_copy(update={"notes": modified_notes})

    report = align_editions(
        original, modified, left_label="edition-a", right_label="edition-b"
    )

    # Must detect the pitch and rhythm variants we introduced
    variant_types = {v.variant_type for v in report.variants}
    assert VariantType.PITCH in variant_types, (
        f"Failed to detect pitch change in {chorale_stem}"
    )
    assert VariantType.RHYTHM in variant_types, (
        f"Failed to detect rhythm change in {chorale_stem}"
    )
    assert report.summary.unchanged_count > 0, "Some notes should remain unchanged"
