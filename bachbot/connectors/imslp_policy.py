from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DistributionDecision:
    allowed_in_public_repo: bool
    reason: str


def evaluate_distribution_rights(*, public_domain_composer: bool, modern_edition: bool, modern_recording: bool) -> DistributionDecision:
    if modern_recording:
        return DistributionDecision(False, "Recordings have separate rights and must stay out of the public repo.")
    if modern_edition:
        return DistributionDecision(False, "Modern editions require local/private storage unless rights are explicit.")
    if public_domain_composer:
        return DistributionDecision(True, "Composer-level public-domain status is compatible with manifest-only public distribution.")
    return DistributionDecision(False, "Distribution rights are unclear; default to private/local storage.")

