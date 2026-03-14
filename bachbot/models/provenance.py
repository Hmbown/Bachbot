from __future__ import annotations

from pydantic import Field

from bachbot.models.base import BachbotModel


class ProvenanceRecord(BachbotModel):
    prov_id: str
    subject_type: str
    subject_id: str
    action: str
    tool_name: str
    tool_version: str | None = None
    operator: str = "bachbot"
    timestamp: str
    input_checksums: list[str] = Field(default_factory=list)
    output_checksums: list[str] = Field(default_factory=list)
    license_snapshot: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
