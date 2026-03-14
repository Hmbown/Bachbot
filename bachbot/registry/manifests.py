from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from bachbot.models.base import BachbotModel


class LicenseInfo(BachbotModel):
    data: str | None = None
    corpus: str | None = None
    site_content: str | None = None
    files: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class DatasetManifest(BachbotModel):
    dataset_id: str
    type: str
    source_url: str
    retrieved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    checksum_policy: str = "sha256"
    notes: list[str] = Field(default_factory=list)
    catalog_revision: str | None = None
    license: LicenseInfo = Field(default_factory=LicenseInfo)
    metadata: dict[str, Any] = Field(default_factory=dict)
    name: str | None = None
    scope: list[str] = Field(default_factory=list)
    api_or_export_notes: list[str] = Field(default_factory=list)
    catalog_context: dict[str, Any] = Field(default_factory=dict)
    storage_policy: dict[str, Any] = Field(default_factory=dict)
    redistribution: dict[str, Any] = Field(default_factory=dict)
    trust_model: dict[str, Any] = Field(default_factory=dict)
    recommended_use: list[str] = Field(default_factory=list)
    provenance_requirements: list[str] = Field(default_factory=list)


def load_manifest(path: str | Path) -> DatasetManifest:
    raw = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix.lower() == ".json":
        payload = json.loads(raw)
    else:
        payload = yaml.safe_load(raw)
    return DatasetManifest.model_validate(payload)


def dump_manifest(manifest: DatasetManifest, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.model_dump(mode="json", exclude_none=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path
