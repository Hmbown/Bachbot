"""Search helpers."""

from __future__ import annotations

from bachbot.claims.bundle import EvidenceBundle
from .query_language import parse_query


def retrieve(bundles: list[EvidenceBundle], query: str) -> list[EvidenceBundle]:
    terms = parse_query(query)
    results = bundles
    for term in terms:
        results = [
            bundle
            for bundle in results
            if term.lower() in bundle.work_id.lower()
            or term.lower() in bundle.section_id.lower()
            or any(term.lower() in entry.lower() for entry in bundle.uncertainties)
        ]
    return results
