from __future__ import annotations

from pathlib import Path

from bachbot.evals import manifest_completeness
from bachbot.registry import CorpusRegistry, DatasetManifest, load_manifest


def test_load_manifest_fixture(fixture_dir: Path) -> None:
    manifest = load_manifest(fixture_dir / "manifest.yaml")
    assert isinstance(manifest, DatasetManifest)
    assert manifest.dataset_id == "test_bach_digital"
    assert manifest.license.data == "ODC PDDL 1.0"


def test_registry_registers_manifest(tmp_path: Path, fixture_dir: Path) -> None:
    registry = CorpusRegistry(index_path=tmp_path / "registry.json")
    entry = registry.register(fixture_dir / "manifest.yaml")
    assert entry.dataset_id == "test_bach_digital"
    entries = registry.list_entries()
    assert len(entries) == 1
    assert entries[0].manifest_type == "authority_metadata"


def test_manifest_completeness_scores_expected_fields(fixture_dir: Path) -> None:
    manifest = load_manifest(fixture_dir / "manifest.yaml")
    assert manifest_completeness(manifest) == 1.0
