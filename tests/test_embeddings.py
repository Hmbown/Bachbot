from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from bachbot.analysis.stats.embeddings import (
    analyze_dataset_embeddings,
    build_embedding_space,
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


def test_build_embedding_space_pads_to_requested_dimension() -> None:
    corpus = [
        _bundle("chorale-a", "major", ["I", "ii", "V", "V7", "I", "vi"]),
        _bundle("chorale-b", "major", ["IV", "ii", "V", "V7", "I", "iii"]),
        _bundle("chorale-c", "minor", ["i", "iv", "iiø7", "V", "i", "VII"], tonic="A"),
        _bundle("chorale-d", "minor", ["i", "VI", "iv", "V", "i", "III"], tonic="D"),
    ]
    space = build_embedding_space(corpus, dataset_id="test", dimension=32)

    assert space.chord_vectors.shape[1] == 32
    assert space.corpus_size == 4
    assert space.diagnostics.related_pair == "V~V7"
    assert np.isfinite(space.diagnostics.related_similarity)
    assert np.isfinite(space.diagnostics.unrelated_similarity)


def test_embeddings_cli_exports_numpy_arrays_and_plot(tmp_path: Path) -> None:
    runner = CliRunner()
    workspace = tmp_path / "workspace"
    derived_root = workspace / "data/derived/dcml_bach_chorales"
    derived_root.mkdir(parents=True)

    bundles = [
        _bundle("chorale-a", "major", ["I", "ii", "V", "V7", "I", "vi"]),
        _bundle("chorale-b", "major", ["IV", "ii", "V", "V7", "I", "iii"]),
        _bundle("chorale-c", "minor", ["i", "iv", "iiø7", "V", "i", "VII"], tonic="A"),
        _bundle("chorale-d", "minor", ["i", "VI", "iv", "V", "i", "III"], tonic="D"),
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

    output_dir = workspace / "exports"
    get_settings.cache_clear()
    previous_cwd = Path.cwd()
    try:
        os.chdir(workspace)
        result = runner.invoke(
            app,
            [
                "analyze",
                "embeddings",
                "--dataset",
                "dcml_bach_chorales",
                "--output-dir",
                str(output_dir),
                "--visualize",
            ],
        )
    finally:
        os.chdir(previous_cwd)
        get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["projection_method"] in {"umap", "linear-fallback"}
    assert Path(payload["chord_vectors_path"]).exists()
    assert Path(payload["chorale_vectors_path"]).exists()
    assert Path(payload["chorale_projection_path"]).exists()
    assert Path(payload["manifest_path"]).exists()
    assert Path(payload["visualization_path"]).exists()
    assert np.load(payload["chord_vectors_path"]).shape[1] == 32
    assert np.load(payload["chorale_vectors_path"]).shape == (4, 32)


@pytest.mark.skipif(not _CORPUS_INDEX.exists(), reason="No corpus embedding source data available")
def test_real_corpus_embeddings_meet_issue_acceptance(tmp_path: Path) -> None:
    manifest = analyze_dataset_embeddings(
        dataset="dcml_bach_chorales",
        output_dir=tmp_path / "embeddings",
        visualize=True,
    )

    assert manifest.dimension == 32
    assert manifest.chord_type_count >= 19
    assert manifest.projection_method in ("umap", "linear-fallback")
    assert manifest.diagnostics.related_similarity > manifest.diagnostics.unrelated_similarity
    assert manifest.diagnostics.mode_separation_ratio > 1.0
    assert Path(manifest.chord_vectors_path).exists()
    assert Path(manifest.chorale_vectors_path).exists()
    assert Path(manifest.visualization_path).exists()

    chord_vectors = np.load(manifest.chord_vectors_path)
    chorale_vectors = np.load(manifest.chorale_vectors_path)
    projection = np.load(manifest.chorale_projection_path)

    assert chord_vectors.shape == (manifest.chord_type_count, 32)
    assert chorale_vectors.shape == (manifest.corpus_size, 32)
    assert projection.shape == (manifest.corpus_size, 2)
