from __future__ import annotations

import json
from pathlib import Path

import pytest

from bachbot.analysis.schenker import analyze_schenkerian
from bachbot.encodings.event_graph import EventGraph

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "schenker_gold_standard.json"


def _load_cases() -> list[dict[str, object]]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: str(case["id"]))
def test_gold_standard_fixture_points_to_exact_bwv(case: dict[str, object]) -> None:
    source_score = _REPO_ROOT / str(case["source_score"])
    score_text = source_score.read_text(encoding="utf-8")

    assert str(case["bwv"]) in score_text
    assert case["published_sources"]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: str(case["id"]))
def test_published_schenker_background_shape(case: dict[str, object]) -> None:
    graph_path = _REPO_ROOT / str(case["graph_path"])
    graph = EventGraph(**json.loads(graph_path.read_text(encoding="utf-8")))

    analysis = analyze_schenkerian(graph)
    soprano_background = [note for note in analysis.background.notes if note.voice_id == "S"]
    middleground_primary_tones = [
        note
        for note in analysis.middleground.notes
        if note.voice_id == "S" and note.scale_degree == int(case["primary_tone_degree"])
    ]

    assert analysis.urlinie.detected is True
    assert analysis.urlinie.degrees == case["expected_background_urlinie"]
    assert [note.scale_degree for note in soprano_background] == case["expected_background_urlinie"]
    assert analysis.bassbrechung.detected is True
    assert analysis.bassbrechung.degrees == case["expected_bassbrechung"]
    assert len(middleground_primary_tones) >= int(case["minimum_primary_tone_count"])
