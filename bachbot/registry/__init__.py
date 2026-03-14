from __future__ import annotations

import json
from pathlib import Path

from bachbot.models.base import BachbotModel
from bachbot.registry.catalog import CorpusCatalog
from bachbot.registry.manifests import DatasetManifest, dump_manifest, load_manifest


class RegistryEntry(BachbotModel):
    dataset_id: str
    manifest_type: str
    source_url: str
    manifest_path: str


class CorpusRegistry:
    def __init__(self, index_path: str | Path) -> None:
        self.index_path = Path(index_path)

    def _load_entries(self) -> list[RegistryEntry]:
        if not self.index_path.exists():
            return []
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        return [RegistryEntry.model_validate(item) for item in payload]

    def _save_entries(self, entries: list[RegistryEntry]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps([entry.model_dump(mode="json") for entry in entries], indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def register(self, manifest_path: str | Path) -> RegistryEntry:
        manifest = load_manifest(manifest_path)
        entry = RegistryEntry(
            dataset_id=manifest.dataset_id,
            manifest_type=manifest.type,
            source_url=manifest.source_url,
            manifest_path=str(Path(manifest_path)),
        )
        entries = [item for item in self._load_entries() if item.dataset_id != entry.dataset_id]
        entries.append(entry)
        entries.sort(key=lambda item: item.dataset_id)
        self._save_entries(entries)
        return entry

    def list_entries(self) -> list[RegistryEntry]:
        return self._load_entries()

    def get_manifest(self, dataset_id: str) -> DatasetManifest:
        for entry in self._load_entries():
            if entry.dataset_id == dataset_id:
                return load_manifest(entry.manifest_path)
        raise KeyError(dataset_id)


__all__ = [
    "CorpusCatalog",
    "CorpusRegistry",
    "DatasetManifest",
    "RegistryEntry",
    "dump_manifest",
    "load_manifest",
]
