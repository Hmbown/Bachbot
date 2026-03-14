from __future__ import annotations

from pathlib import Path

from bachbot.composition import compose_chorale_study
from bachbot.composition.validators.hard_rules import validate_graph
from bachbot.encodings import Normalizer
from bachbot.exports import export_json, export_musicxml


def test_compose_and_export_chorale_study(tmp_path: Path) -> None:
    melody = Normalizer().normalize("tests/fixtures/chorales/simple_cantus.musicxml", work_id="MELODY-TEST")
    graph, artifact, report = compose_chorale_study(melody)
    validation = validate_graph(graph)

    musicxml_path = export_musicxml(graph, tmp_path / "study.musicxml")
    json_path = export_json({"artifact": artifact.model_dump(mode="json"), "report": report}, tmp_path / "study.json")

    assert len(graph.voices) == 4
    assert validation.passed is True
    assert report["plan"]["key"] == "C"
    assert musicxml_path.exists()
    assert json_path.exists()
