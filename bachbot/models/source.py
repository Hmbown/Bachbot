"""Source models."""

from __future__ import annotations

from pydantic import Field

from .base import BachbotModel


class DigitalManifest(BachbotModel):
    source_url: str | None = None
    exports: dict[str, str] = Field(default_factory=dict)
    checksum_policy: str = "sha256"
    last_changed: str | None = None


class Source(BachbotModel):
    source_id: str
    repository: str | None = None
    shelfmark: str | None = None
    siglum: str | None = None
    source_type: str | None = None
    date_range: str | None = None
    scribe_or_copyist: str | None = None
    watermark_refs: list[str] = Field(default_factory=list)
    bach_digital_ref: str | None = None
    rism_ref: str | None = None
    digital_manifest: DigitalManifest = Field(default_factory=DigitalManifest)
    license: str | None = None
    quality_notes: list[str] = Field(default_factory=list)
