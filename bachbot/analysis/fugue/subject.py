from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph
from bachbot.features.intervals import melodic_intervals


def _occurrence_payload(*, graph: EventGraph, voice_id: str, start_index: int, pattern_length: int) -> dict[str, object] | None:
    events = graph.voice_events(voice_id)
    window = events[start_index : start_index + pattern_length + 1]
    if len(window) < pattern_length + 1:
        return None
    end_note = window[-1]
    return {
        "voice_id": voice_id,
        "start_index": start_index,
        "end_index": start_index + pattern_length,
        "start_onset": window[0].offset_quarters,
        "end_onset": end_note.offset_quarters + end_note.duration_quarters,
        "start_measure": window[0].measure_number,
        "end_measure": end_note.measure_number,
        "start_beat": window[0].beat,
        "end_beat": end_note.beat + end_note.duration_quarters,
        "pitches": [note.midi for note in window],
    }


def detect_subject_candidates(graph: EventGraph, min_length: int = 4) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    voice_intervals = {voice_id: melodic_intervals(graph, voice_id) for voice_id in graph.ordered_voice_ids()}
    seen: dict[tuple[int, ...], dict[str, object]] = {}
    for voice_id, intervals in voice_intervals.items():
        for index in range(max(len(intervals) - min_length + 1, 0)):
            pattern = tuple(intervals[index : index + min_length])
            occurrence = _occurrence_payload(graph=graph, voice_id=voice_id, start_index=index, pattern_length=min_length)
            if occurrence is None:
                continue
            if pattern in seen:
                seen[pattern]["occurrences"].append(occurrence)
            else:
                seen[pattern] = {"pattern": pattern, "occurrences": [occurrence], "type": "subject_candidate"}
    for payload in seen.values():
        payload["occurrences"].sort(key=lambda item: (item["start_onset"], item["voice_id"]))
        for entry_order, occurrence in enumerate(payload["occurrences"], start=1):
            occurrence["entry_order"] = entry_order
        if len({occurrence["voice_id"] for occurrence in payload["occurrences"]}) > 1:
            findings.append(payload)
    return findings
