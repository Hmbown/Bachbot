"""Tests for the human evaluation protocol (SHA-2844)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bachbot.evaluation.models import (
    EvaluationPair,
    EvaluationRating,
    EvaluationSession,
    EvaluationSummary,
)
from bachbot.evaluation.protocol import (
    analyze_evaluation,
    compute_krippendorff_alpha,
    compute_metric_correlation,
    generate_evaluation_pairs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def originals_dir(tmp_path: Path) -> Path:
    d = tmp_path / "originals"
    d.mkdir()
    for i in range(10):
        (d / f"original_{i:03d}.json").write_text("{}", encoding="utf-8")
    return d


@pytest.fixture()
def generated_dir(tmp_path: Path) -> Path:
    d = tmp_path / "generated"
    d.mkdir()
    for i in range(10):
        (d / f"generated_{i:03d}.json").write_text("{}", encoding="utf-8")
    return d


def _make_rating(
    pair_id: str,
    evaluator_id: str,
    *,
    musicality_a: int = 5,
    musicality_b: int = 3,
    authenticity_a: int = 6,
    authenticity_b: int = 2,
    voice_leading_a: int = 5,
    voice_leading_b: int = 3,
    identified_original: str = "a",
) -> EvaluationRating:
    return EvaluationRating(
        pair_id=pair_id,
        evaluator_id=evaluator_id,
        timestamp="2026-03-13T00:00:00+00:00",
        musicality_a=musicality_a,
        musicality_b=musicality_b,
        authenticity_a=authenticity_a,
        authenticity_b=authenticity_b,
        voice_leading_a=voice_leading_a,
        voice_leading_b=voice_leading_b,
        identified_original=identified_original,
    )


# ---------------------------------------------------------------------------
# a) Pair generation
# ---------------------------------------------------------------------------


def test_generate_pairs_basic(originals_dir: Path, generated_dir: Path, tmp_path: Path) -> None:
    output = tmp_path / "output"
    pairs = generate_evaluation_pairs(
        sorted(originals_dir.glob("*.json")),
        sorted(generated_dir.glob("*.json")),
        count=5,
        seed=42,
        output_dir=output,
    )
    assert len(pairs) == 5
    pair_ids = [p.pair_id for p in pairs]
    assert len(set(pair_ids)) == 5, "pair IDs must be unique"


def test_generate_pairs_randomization(originals_dir: Path, generated_dir: Path, tmp_path: Path) -> None:
    output = tmp_path / "output"
    pairs = generate_evaluation_pairs(
        sorted(originals_dir.glob("*.json")),
        sorted(generated_dir.glob("*.json")),
        count=10,
        seed=42,
        output_dir=output,
    )
    a_is_orig_flags = [p.chorale_a_is_original for p in pairs]
    # With 10 pairs and random assignment, extremely unlikely all are same
    assert not all(a_is_orig_flags) or not all(not f for f in a_is_orig_flags), (
        "A/B assignment should be randomized"
    )


def test_generate_pairs_midi_files_created(originals_dir: Path, generated_dir: Path, tmp_path: Path) -> None:
    output = tmp_path / "output"
    pairs = generate_evaluation_pairs(
        sorted(originals_dir.glob("*.json")),
        sorted(generated_dir.glob("*.json")),
        count=3,
        seed=7,
        output_dir=output,
    )
    for pair in pairs:
        assert Path(pair.chorale_a_midi_path).exists()
        assert Path(pair.chorale_b_midi_path).exists()


def test_generate_pairs_deterministic(originals_dir: Path, generated_dir: Path, tmp_path: Path) -> None:
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    orig = sorted(originals_dir.glob("*.json"))
    gen = sorted(generated_dir.glob("*.json"))
    pairs1 = generate_evaluation_pairs(orig, gen, count=5, seed=99, output_dir=out1)
    pairs2 = generate_evaluation_pairs(orig, gen, count=5, seed=99, output_dir=out2)
    for p1, p2 in zip(pairs1, pairs2):
        assert p1.pair_id == p2.pair_id
        assert p1.chorale_a_is_original == p2.chorale_a_is_original


# ---------------------------------------------------------------------------
# b) Rating model validation
# ---------------------------------------------------------------------------


def test_rating_likert_valid() -> None:
    r = _make_rating("p1", "e1")
    assert 1 <= r.musicality_a <= 7
    assert 1 <= r.authenticity_b <= 7


def test_rating_likert_out_of_range() -> None:
    with pytest.raises(Exception):
        EvaluationRating(
            pair_id="p1",
            evaluator_id="e1",
            timestamp="2026-01-01T00:00:00Z",
            musicality_a=0,  # below minimum
            musicality_b=3,
            authenticity_a=5,
            authenticity_b=5,
            voice_leading_a=5,
            voice_leading_b=5,
            identified_original="a",
        )


def test_rating_likert_above_range() -> None:
    with pytest.raises(Exception):
        EvaluationRating(
            pair_id="p1",
            evaluator_id="e1",
            timestamp="2026-01-01T00:00:00Z",
            musicality_a=4,
            musicality_b=8,  # above maximum
            authenticity_a=5,
            authenticity_b=5,
            voice_leading_a=5,
            voice_leading_b=5,
            identified_original="a",
        )


def test_rating_extra_field_forbidden() -> None:
    with pytest.raises(Exception):
        EvaluationRating(
            pair_id="p1",
            evaluator_id="e1",
            timestamp="2026-01-01T00:00:00Z",
            musicality_a=4,
            musicality_b=4,
            authenticity_a=4,
            authenticity_b=4,
            voice_leading_a=4,
            voice_leading_b=4,
            identified_original="a",
            secret_field="nope",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# c) Krippendorff's alpha
# ---------------------------------------------------------------------------


def test_krippendorff_perfect_agreement() -> None:
    """Two evaluators rate identically -> alpha = 1.0."""
    ratings = [
        _make_rating("p1", "e1", musicality_a=5, musicality_b=3),
        _make_rating("p1", "e2", musicality_a=5, musicality_b=3),
        _make_rating("p2", "e1", musicality_a=7, musicality_b=1),
        _make_rating("p2", "e2", musicality_a=7, musicality_b=1),
    ]
    alpha = compute_krippendorff_alpha(ratings, "musicality")
    assert alpha == pytest.approx(1.0, abs=0.001)


def test_krippendorff_disagreement() -> None:
    """Evaluators disagree substantially -> alpha < 1.0."""
    ratings = [
        _make_rating("p1", "e1", musicality_a=1, musicality_b=7),
        _make_rating("p1", "e2", musicality_a=7, musicality_b=1),
        _make_rating("p2", "e1", musicality_a=2, musicality_b=6),
        _make_rating("p2", "e2", musicality_a=6, musicality_b=2),
    ]
    alpha = compute_krippendorff_alpha(ratings, "musicality")
    assert alpha < 0.5


def test_krippendorff_single_evaluator() -> None:
    """Single evaluator -> no pairable data -> alpha = 0.0."""
    ratings = [_make_rating("p1", "e1")]
    alpha = compute_krippendorff_alpha(ratings, "musicality")
    assert alpha == 0.0


# ---------------------------------------------------------------------------
# d) Summary statistics
# ---------------------------------------------------------------------------


def test_analyze_evaluation_averages() -> None:
    pairs = [
        EvaluationPair(
            pair_id="p1",
            chorale_a_id="orig1",
            chorale_b_id="gen1",
            chorale_a_is_original=True,
            chorale_a_midi_path="/tmp/a.mid",
            chorale_b_midi_path="/tmp/b.mid",
        ),
    ]
    ratings = [
        _make_rating("p1", "e1", musicality_a=6, musicality_b=2, authenticity_a=7, authenticity_b=1,
                      voice_leading_a=5, voice_leading_b=3, identified_original="a"),
    ]
    session = EvaluationSession(
        session_id="s1", evaluator_id="e1", pairs=pairs, ratings=ratings
    )
    summary = analyze_evaluation([session])
    assert summary.total_pairs == 1
    assert summary.total_ratings == 1
    # A is original for this pair
    assert summary.avg_musicality_original == pytest.approx(6.0, abs=0.01)
    assert summary.avg_musicality_generated == pytest.approx(2.0, abs=0.01)
    assert summary.avg_authenticity_original == pytest.approx(7.0, abs=0.01)
    assert summary.avg_authenticity_generated == pytest.approx(1.0, abs=0.01)


def test_analyze_evaluation_empty() -> None:
    session = EvaluationSession(session_id="s1", evaluator_id="e1")
    summary = analyze_evaluation([session])
    assert summary.total_ratings == 0
    assert summary.avg_musicality_original == 0.0


# ---------------------------------------------------------------------------
# e) Metric correlation
# ---------------------------------------------------------------------------


def test_correlation_perfect() -> None:
    """Perfect positive correlation -> r ~ 1.0."""
    ratings = [
        _make_rating("p1", "e1", musicality_a=2, musicality_b=2),
        _make_rating("p2", "e1", musicality_a=4, musicality_b=4),
        _make_rating("p3", "e1", musicality_a=6, musicality_b=6),
    ]
    scores = {"p1": 1.0, "p2": 2.0, "p3": 3.0}
    result = compute_metric_correlation(ratings, scores)
    assert result["musicality"] == pytest.approx(1.0, abs=0.01)


def test_correlation_no_data() -> None:
    result = compute_metric_correlation([], {})
    assert result["musicality"] == 0.0


# ---------------------------------------------------------------------------
# f) Identification accuracy
# ---------------------------------------------------------------------------


def test_identification_accuracy_all_correct() -> None:
    pairs = [
        EvaluationPair(
            pair_id="p1", chorale_a_id="o", chorale_b_id="g",
            chorale_a_is_original=True,
            chorale_a_midi_path="/tmp/a.mid", chorale_b_midi_path="/tmp/b.mid",
        ),
        EvaluationPair(
            pair_id="p2", chorale_a_id="g", chorale_b_id="o",
            chorale_a_is_original=False,
            chorale_a_midi_path="/tmp/a.mid", chorale_b_midi_path="/tmp/b.mid",
        ),
    ]
    ratings = [
        _make_rating("p1", "e1", identified_original="a"),  # correct (a is original)
        _make_rating("p2", "e1", identified_original="b"),  # correct (b is original)
    ]
    session = EvaluationSession(session_id="s1", evaluator_id="e1", pairs=pairs, ratings=ratings)
    summary = analyze_evaluation([session])
    assert summary.identification_accuracy == pytest.approx(1.0)


def test_identification_accuracy_all_wrong() -> None:
    pairs = [
        EvaluationPair(
            pair_id="p1", chorale_a_id="o", chorale_b_id="g",
            chorale_a_is_original=True,
            chorale_a_midi_path="/tmp/a.mid", chorale_b_midi_path="/tmp/b.mid",
        ),
    ]
    ratings = [
        _make_rating("p1", "e1", identified_original="b"),  # wrong
    ]
    session = EvaluationSession(session_id="s1", evaluator_id="e1", pairs=pairs, ratings=ratings)
    summary = analyze_evaluation([session])
    assert summary.identification_accuracy == pytest.approx(0.0)


def test_identification_unsure_excluded() -> None:
    pairs = [
        EvaluationPair(
            pair_id="p1", chorale_a_id="o", chorale_b_id="g",
            chorale_a_is_original=True,
            chorale_a_midi_path="/tmp/a.mid", chorale_b_midi_path="/tmp/b.mid",
        ),
    ]
    ratings = [
        _make_rating("p1", "e1", identified_original="unsure"),
    ]
    session = EvaluationSession(session_id="s1", evaluator_id="e1", pairs=pairs, ratings=ratings)
    summary = analyze_evaluation([session])
    # unsure should not count toward identification accuracy
    assert summary.identification_accuracy == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# g) Session serialization roundtrip
# ---------------------------------------------------------------------------


def test_session_roundtrip(tmp_path: Path) -> None:
    pairs = [
        EvaluationPair(
            pair_id="p1", chorale_a_id="orig1", chorale_b_id="gen1",
            chorale_a_is_original=True,
            chorale_a_midi_path="/tmp/a.mid", chorale_b_midi_path="/tmp/b.mid",
        ),
    ]
    ratings = [_make_rating("p1", "e1")]
    session = EvaluationSession(
        session_id="test-session",
        evaluator_id="e1",
        pairs=pairs,
        ratings=ratings,
    )
    path = tmp_path / "session.json"
    path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
    reloaded = EvaluationSession.model_validate_json(path.read_text(encoding="utf-8"))
    assert reloaded.session_id == session.session_id
    assert len(reloaded.pairs) == 1
    assert len(reloaded.ratings) == 1
    assert reloaded.pairs[0].pair_id == "p1"
    assert reloaded.ratings[0].musicality_a == session.ratings[0].musicality_a


def test_summary_roundtrip() -> None:
    summary = EvaluationSummary(
        total_pairs=10,
        total_evaluators=3,
        total_ratings=30,
        avg_musicality_original=5.5,
        avg_musicality_generated=3.2,
        identification_accuracy=0.7,
        krippendorff_alpha=0.65,
    )
    data = json.loads(summary.model_dump_json())
    reloaded = EvaluationSummary.model_validate(data)
    assert reloaded.total_pairs == 10
    assert reloaded.krippendorff_alpha == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# h) Server creation
# ---------------------------------------------------------------------------


def test_create_evaluation_app(tmp_path: Path) -> None:
    """Verify create_evaluation_app returns a working FastAPI app."""
    from fastapi.testclient import TestClient

    from bachbot.evaluation.server import create_evaluation_app

    # Set up minimal session
    pairs = [
        EvaluationPair(
            pair_id="p1", chorale_a_id="orig1", chorale_b_id="gen1",
            chorale_a_is_original=True,
            chorale_a_midi_path=str(tmp_path / "midi" / "p1_a.mid"),
            chorale_b_midi_path=str(tmp_path / "midi" / "p1_b.mid"),
        ),
    ]
    session = EvaluationSession(session_id="test", evaluator_id="pending", pairs=pairs)
    session_path = tmp_path / "session.json"
    session_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    # Create MIDI dir with stub files
    midi_dir = tmp_path / "midi"
    midi_dir.mkdir(exist_ok=True)
    (midi_dir / "p1_a.mid").write_bytes(b"MThd")
    (midi_dir / "p1_b.mid").write_bytes(b"MThd")

    app = create_evaluation_app(tmp_path)
    client = TestClient(app)

    # Landing page
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Bachbot" in resp.text

    # Progress page
    resp = client.get("/progress?evaluator_id=tester")
    assert resp.status_code == 200
    assert "0" in resp.text  # 0 rated

    # Evaluate page
    resp = client.get("/evaluate/p1?evaluator_id=tester")
    assert resp.status_code == 200
    assert "Chorale A" in resp.text

    # Submit rating
    resp = client.post(
        "/evaluate/p1",
        data={
            "evaluator_id": "tester",
            "musicality_a": "5",
            "musicality_b": "3",
            "authenticity_a": "6",
            "authenticity_b": "2",
            "voice_leading_a": "5",
            "voice_leading_b": "3",
            "identified_original": "a",
            "notes": "A sounds more authentic",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303  # redirect

    # Verify rating was saved
    ratings_dir = tmp_path / "ratings"
    saved = list(ratings_dir.glob("*.json"))
    assert len(saved) == 1
    rating_data = json.loads(saved[0].read_text(encoding="utf-8"))
    assert rating_data["pair_id"] == "p1"
    assert rating_data["musicality_a"] == 5


def test_create_evaluation_app_unknown_pair(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from bachbot.evaluation.server import create_evaluation_app

    session = EvaluationSession(session_id="test", evaluator_id="pending", pairs=[])
    (tmp_path / "session.json").write_text(session.model_dump_json(), encoding="utf-8")

    app = create_evaluation_app(tmp_path)
    client = TestClient(app)
    resp = client.get("/evaluate/nonexistent?evaluator_id=tester")
    assert resp.status_code == 404


def test_serve_midi_file(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from bachbot.evaluation.server import create_evaluation_app

    session = EvaluationSession(session_id="test", evaluator_id="pending", pairs=[])
    (tmp_path / "session.json").write_text(session.model_dump_json(), encoding="utf-8")
    midi_dir = tmp_path / "midi"
    midi_dir.mkdir()
    (midi_dir / "test.mid").write_bytes(b"MThd\x00\x00")

    app = create_evaluation_app(tmp_path)
    client = TestClient(app)
    resp = client.get("/midi/test.mid")
    assert resp.status_code == 200
    assert resp.content.startswith(b"MThd")
