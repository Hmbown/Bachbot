from __future__ import annotations

from pathlib import Path

from bachbot.evals import manifest_completeness
from bachbot.registry import CorpusRegistry, dump_manifest, load_manifest


def test_manifest_roundtrip(tmp_path: Path) -> None:
    manifest = load_manifest("data/manifests/bach_digital.yaml")
    out = dump_manifest(manifest, tmp_path / "bach_digital_copy.yaml")
    reloaded = load_manifest(out)
    assert reloaded.dataset_id == "bach_digital"
    assert manifest_completeness(reloaded) >= 0.8


def test_registry_registers_dataset_manifest(tmp_path: Path) -> None:
    registry = CorpusRegistry(index_path=tmp_path / "registry.json")
    entry = registry.register("data/manifests/rism.yaml")
    loaded = registry.get_manifest("rism")
    assert entry.dataset_id == "rism"
    assert loaded.dataset_id == "rism"
