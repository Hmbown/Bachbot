from __future__ import annotations

from bachbot.analysis.harmony.verticalities import build_verticalities
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.cadence import Cadence


def infer_phrase_endings(graph: EventGraph, cadences: list[Cadence] | None = None) -> list[dict[str, object]]:
    by_measure: dict[int, object] = {}
    for slice_ in build_verticalities(graph):
        by_measure[slice_.measure_number] = slice_
    endings: list[dict[str, object]] = []
    seen_measures: set[int] = set()

    # Primary: fermata-based phrase endings
    for measure, slice_ in sorted(by_measure.items()):
        evidence: list[str] = []
        strength = 0.0
        if any(note.fermata for note in slice_.active_notes):
            strength += 0.75
            evidence.append("fermata")
        if slice_.duration >= 1.0:
            strength += 0.15
            evidence.append("long_terminal_sonority")
        if strength >= 0.6:
            endings.append({"measure": measure, "type": "phrase_end", "strength": round(min(strength, 0.99), 2), "evidence": evidence})
            seen_measures.add(measure)

    # Fallback: cadence-based phrase endings when fermata data is unavailable
    if not endings and cadences:
        for cad in cadences:
            measure_str = cad.ref_id.rsplit(":m", 1)[-1] if ":m" in cad.ref_id else None
            if measure_str is None:
                continue
            try:
                measure = int(measure_str)
            except ValueError:
                continue
            if measure not in seen_measures:
                endings.append({
                    "measure": measure,
                    "type": cad.cadence_type,
                    "strength": cad.strength,
                    "evidence": cad.voice_leading_evidence,
                })
                seen_measures.add(measure)

    return endings


def phrase_end_measures(graph: EventGraph, cadences: list[Cadence] | None = None) -> list[int]:
    return [item["measure"] for item in infer_phrase_endings(graph, cadences=cadences)]
