"""Runtime configuration for Bachbot."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class BachbotSettings(BaseModel):
    """Filesystem-oriented settings for local-first workflows."""

    model_config = ConfigDict(frozen=True)

    workspace_root: Path = Field(default_factory=lambda: Path.cwd())
    data_dir: Path = Field(default_factory=lambda: Path.cwd() / "data")
    cache_dir: Path = Field(default_factory=lambda: Path.cwd() / "cache")
    manifests_dir: Path = Field(default_factory=lambda: Path.cwd() / "data" / "manifests")
    raw_dir: Path = Field(default_factory=lambda: Path.cwd() / "data" / "raw")
    normalized_dir: Path = Field(default_factory=lambda: Path.cwd() / "data" / "normalized")
    derived_dir: Path = Field(default_factory=lambda: Path.cwd() / "data" / "derived")
    private_dir: Path = Field(default_factory=lambda: Path.cwd() / "data" / "private")

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.cache_dir,
            self.manifests_dir,
            self.raw_dir,
            self.normalized_dir,
            self.derived_dir,
            self.private_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> BachbotSettings:
    settings = BachbotSettings()
    settings.ensure_dirs()
    return settings
