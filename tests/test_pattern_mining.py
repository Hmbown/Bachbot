from __future__ import annotations

import json
import os
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bachbot.analysis.stats.patterns import (
    _extract_primary_roman_sequence,
    filter_patterns,
    mine_dataset_patterns,
    mine_patterns,
)
from bachbot.cli.main import app
from bachbot.config import get_settings

_CORPUS_INDEX = Path("data/derived/dcml_bach_chorales/analysis_index.json")


def _bundle(work_id: str, mode: str, labels: list[str], *, tonic: str = "C") -> dict:
    harmony = []
    for index, label in enumerate(labels, start=1):
        harmony.append(
            {
                "harmonic_event_id": f"{work_id}:h{index}:{index * 100}",
                "ref_id": f"{work_id}:m{index}",
                "onset": float(index - 1),
                "roman_numeral_candidate_set": [label],
                "local_key": f"{tonic} {mode}",
                "global_key": f"{tonic} {mode}",
            }
        )
    return {
        "work_id": work_id,
        "metadata": {
            "encoding_id": work_id,
            "key": f"{tonic} {mode}",
            "key_mode": mode,
            "key_tonic": tonic,
        },
        "deterministic_findings": {"harmony": harmony},
    }


def test_extract_primary_roman_sequence_collapses_repeats() -> None:
    bundle = _bundle("chorale-a", "major", ["I", "I", "V", "V", "V7", "I"])
    sequence = _extract_primary_roman_sequence(bundle, collapse_repeats=True)
    assert [event["label"] for event in sequence] == ["I", "V", "V7", "I"]
    assert [event["measure"] for event in sequence] == [1, 3, 5, 6]


def test_mine_patterns_counts_occurrences_and_significance() -> None:
    corpus = [
        _bundle("chorale-a", "major", ["I", "ii7", "V", "V7", "I"]),
        _bundle("chorale-b", "major", ["IV", "I", "ii7", "V", "V7", "I"]),
        _bundle("chorale-c", "major", ["I", "ii7", "V", "V7", "I"]),
        _bundle("chorale-d", "major", ["I", "vi", "ii7", "V", "I"]),
    ]
    index = mine_patterns(
        corpus,
        ngram=4,
        dataset_id="test",
        min_count=3,
        min_work_count=3,
        min_pmi=0.0,
        null_trials=16,
    )
    target = filter_patterns(index, pattern="ii7-V-V7-I")[0]
    assert target.count == 3
    assert target.work_count == 3
    assert target.significant is True
    assert target.occurrences[0].start_measure == 2
    singleton = filter_patterns(index, pattern="I-vi-ii7-V")[0]
    assert singleton.count == 1
    assert singleton.significant is False


def test_mine_patterns_honors_mode_filter() -> None:
    corpus = [
        _bundle("chorale-major", "major", ["I", "V", "V7", "I"]),
        _bundle("chorale-minor", "minor", ["i", "iiø7", "V", "i"], tonic="A"),
    ]
    index = mine_patterns(corpus, ngram=4, dataset_id="test", mode="minor", min_count=1, min_pmi=0.0)
    assert index.corpus_size == 1
    assert [summary.pattern for summary in index.patterns] == ["i-iiø7-V-i"]


def test_random_corpus_does_not_mark_sparse_patterns_significant() -> None:
    rng = random.Random(7)
    vocabulary = ["I", "V", "ii7", "vi", "IV", "V7"]
    weights = [8, 8, 3, 3, 2, 2]
    corpus = [
        _bundle(f"random-{index}", "major", rng.choices(vocabulary, weights=weights, k=10))
        for index in range(24)
    ]
    index = mine_patterns(corpus, ngram=4, dataset_id="random", null_trials=24)
    assert not any(summary.significant for summary in index.patterns if summary.count <= 3)


def test_corpus_patterns_cli_outputs_frequency_table(tmp_path: Path) -> None:
    runner = CliRunner()
    workspace = tmp_path / "workspace"
    derived_root = workspace / "data/derived/dcml_bach_chorales"
    derived_root.mkdir(parents=True)

    bundles = [
        _bundle("chorale-a", "major", ["I", "ii7", "V", "V7", "I"]),
        _bundle("chorale-b", "major", ["IV", "I", "ii7", "V", "V7", "I"]),
    ]
    analyses = []
    for bundle in bundles:
        bundle_path = derived_root / f"{bundle['work_id']}.evidence_bundle.json"
        bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        analyses.append({"bundle_path": str(bundle_path)})

    (derived_root / "analysis_index.json").write_text(
        json.dumps({"analysis_count": len(analyses), "analyses": analyses}, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    get_settings.cache_clear()
    previous_cwd = Path.cwd()
    try:
        os.chdir(workspace)
        result = runner.invoke(app, ["corpus", "patterns", "--ngram", "4"])
    finally:
        os.chdir(previous_cwd)
        get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    assert "pattern\tcount\tworks\tsupport\tpmi\tsignificant" in result.output
    assert "ii7-V-V7-I" in result.output
    assert (derived_root / "pattern_index.4gram.json").exists()


@pytest.mark.skipif(not _CORPUS_INDEX.exists(), reason="No corpus pattern-mining source data available")
def test_real_corpus_top_patterns_include_common_bach_idioms(tmp_path: Path) -> None:
    index, _ = mine_dataset_patterns(
        dataset="dcml_bach_chorales",
        ngram=4,
        output=tmp_path / "pattern_index.json",
    )
    top_patterns = {summary.pattern for summary in index.patterns[:20]}
    assert top_patterns & {
        "I-V-V7-I",
        "ii7-V-V7-I",
        "i-iiø7-V-V7",
        "iiø7-V-V7-i",
    }


@pytest.mark.skipif(not _CORPUS_INDEX.exists(), reason="No corpus pattern-mining source data available")
def test_real_corpus_sparse_patterns_are_not_significant(tmp_path: Path) -> None:
    index, _ = mine_dataset_patterns(
        dataset="dcml_bach_chorales",
        ngram=4,
        output=tmp_path / "pattern_index.json",
    )
    assert not any(summary.significant for summary in index.patterns if summary.count <= 3)
