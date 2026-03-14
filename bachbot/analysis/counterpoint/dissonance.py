from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph


def _is_continuation(left, middle) -> bool:
    if left.midi is None or middle.midi is None or left.midi != middle.midi:
        return False
    contiguous = abs((left.offset_quarters + left.duration_quarters) - middle.offset_quarters) < 1e-6
    if left.tie_start or middle.tie_stop:
        return True
    return contiguous and left.measure_number != middle.measure_number


def detect_suspensions(graph: EventGraph) -> list[dict[str, str | int]]:
    findings: list[dict[str, str | int]] = []
    for voice_id, notes in graph.notes_by_voice().items():
        pitched = [note for note in notes if note.midi is not None and not note.is_rest]
        for left, middle, right in zip(pitched, pitched[1:], pitched[2:]):
            contiguous_resolution = abs((middle.offset_quarters + middle.duration_quarters) - right.offset_quarters) < 1e-6
            if _is_continuation(left, middle):
                if contiguous_resolution and right.midi is not None and middle.midi - right.midi in {1, 2}:
                    findings.append({"voice": voice_id, "measure": middle.measure_number, "type": "possible_suspension"})
    return findings
