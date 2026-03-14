"""Basic overlap guard for generated studies."""

from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph
from bachbot.features.motif_vectors import motif_vector


def overlap_score(candidate: EventGraph, reference: EventGraph, voice_id: str = "S") -> float:
    candidate_vectors = set(motif_vector(candidate, voice_id))
    reference_vectors = set(motif_vector(reference, voice_id))
    if not candidate_vectors or not reference_vectors:
        return 0.0
    return len(candidate_vectors & reference_vectors) / len(candidate_vectors | reference_vectors)
