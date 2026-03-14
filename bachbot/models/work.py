"""Work models."""

from __future__ import annotations

from pydantic import Field

from .base import AuthenticityStatus, BachbotModel
from .refs import CatalogId


class Work(BachbotModel):
    work_id: str
    catalog_ids: list[CatalogId] = Field(default_factory=list)
    canonical_title: str
    alternate_titles: list[str] = Field(default_factory=list)
    genre: str | None = None
    scoring: list[str] = Field(default_factory=list)
    date_range: str | None = None
    authenticity_status: AuthenticityStatus = AuthenticityStatus.AUTHENTIC
    period_guess: str | None = None
    liturgical_context: str | None = None
    text_source_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    edition_refs: list[str] = Field(default_factory=list)
    encoding_refs: list[str] = Field(default_factory=list)
