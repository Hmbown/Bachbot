"""Filesystem storage helpers."""

from __future__ import annotations

from pathlib import Path

from bachbot.config import get_settings
from bachbot.models.base import BachbotModel


class StorageRecord(BachbotModel):
    dataset_id: str
    raw_dir: str
    normalized_dir: str
    derived_dir: str
    private_dir: str


class BachbotStorage:
    """Resolve local filesystem paths for a dataset."""

    def __init__(self, dataset_id: str) -> None:
        self.dataset_id = dataset_id
        self.settings = get_settings()

    def ensure(self) -> StorageRecord:
        roots = {
            "raw_dir": self.settings.raw_dir / self.dataset_id,
            "normalized_dir": self.settings.normalized_dir / self.dataset_id,
            "derived_dir": self.settings.derived_dir / self.dataset_id,
            "private_dir": self.settings.private_dir / self.dataset_id,
        }
        for path in roots.values():
            Path(path).mkdir(parents=True, exist_ok=True)
        return StorageRecord(
            dataset_id=self.dataset_id,
            raw_dir=str(roots["raw_dir"]),
            normalized_dir=str(roots["normalized_dir"]),
            derived_dir=str(roots["derived_dir"]),
            private_dir=str(roots["private_dir"]),
        )

