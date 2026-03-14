from __future__ import annotations

import json
import subprocess
import shutil
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bachbot.cli.main import app
from bachbot.encodings import EventGraph, Normalizer
from bachbot.exports.lilypond_export import _pitch_to_lily, event_graph_to_lilypond
from bachbot.models.base import TypedNote


def test_event_graph_to_lilypond_renders_standard_chorale_score(simple_chorale_graph) -> None:
    rendered = simple_chorale_graph.to_lilypond()

    assert "\\clef treble" in rendered
    assert "\\clef bass" in rendered
    assert "\\new FiguredBass" in rendered
    assert "\\time 4/4" in rendered


def test_lilypond_export_includes_fermata_markup(simple_chorale_graph) -> None:
    graph = simple_chorale_graph.model_copy(deep=True)
    graph.notes[0].fermata = True
    rendered = event_graph_to_lilypond(graph)

    assert "\\fermata" in rendered


def test_pitch_to_lily_uses_midi_for_dcml_octaves() -> None:
    note = TypedNote(
        pitch="D55",
        midi=74,
        duration_quarters=1.0,
        offset_quarters=0.0,
        measure_number=1,
        beat=1.0,
        voice_id="S",
    )

    assert _pitch_to_lily(note) == "d''"


def test_real_dcml_graph_renders_sane_octaves() -> None:
    path = Path("data/normalized/dcml_bach_chorales/notes__269 Jesu, der du meine Seele.event_graph.json")
    graph = EventGraph.model_validate(json.loads(path.read_text(encoding="utf-8")))

    rendered = event_graph_to_lilypond(graph)

    assert "d''4" in rendered
    assert "bes8" in rendered
    assert "''''''''" not in rendered


@pytest.mark.skipif(shutil.which("lilypond") is None, reason="lilypond not installed")
def test_export_cli_lilypond_writes_score_and_pdf(tmp_path: Path) -> None:
    output_path = tmp_path / "BWV269.ly"
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "bachbot",
            "export",
            "--format",
            "lilypond",
            "BWV269",
            "--output",
            str(output_path),
            "--pdf",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    pdf_path = output_path.with_suffix(".pdf")
    assert pdf_path.exists()

    rendered = output_path.read_text(encoding="utf-8")
    assert "\\key g \\minor" in rendered
    assert "\\time 4/4" in rendered
    assert "_\\markup" in rendered
    assert "\\new FiguredBass" in rendered
    assert "\\breathe" in rendered


def test_bwv_reference_resolves_normalized_chorale() -> None:
    path = Path("data/normalized/dcml_bach_chorales/notes__269 Jesu, der du meine Seele.event_graph.json")
    graph = EventGraph.model_validate(json.loads(path.read_text(encoding="utf-8")))
    rendered = event_graph_to_lilypond(graph)

    assert "Jesu, der du meine Seele" in rendered
