"""License policy helpers."""

from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class LicensePolicy(BachbotModel):
    dataset_id: str
    metadata_license: str | None = None
    content_license: str | None = None
    redistribution_allowed: bool = False
    notes: list[str] = Field(default_factory=list)


def license_summary(policy: LicensePolicy) -> str:
    content = policy.content_license or "unspecified"
    metadata = policy.metadata_license or "unspecified"
    redistribution = "allowed" if policy.redistribution_allowed else "restricted"
    return f"metadata={metadata}; content={content}; redistribution={redistribution}"

