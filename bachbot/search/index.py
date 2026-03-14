"""In-memory passage index."""

from __future__ import annotations

from bachbot.claims.bundle import EvidenceBundle


class PassageIndex:
    def __init__(self) -> None:
        self.bundles: list[EvidenceBundle] = []

    def add(self, bundle: EvidenceBundle) -> None:
        self.bundles.append(bundle)

    def search(self, token: str) -> list[EvidenceBundle]:
        lowered = token.lower()
        return [
            bundle
            for bundle in self.bundles
            if lowered in bundle.work_id.lower()
            or lowered in bundle.section_id.lower()
            or any(lowered in uncertainty.lower() for uncertainty in bundle.uncertainties)
        ]
