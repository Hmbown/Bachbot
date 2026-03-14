from __future__ import annotations

from bachbot.analysis.fugue.subject import detect_subject_candidates
from bachbot.encodings.event_graph import EventGraph


def _measure_after_offset(graph: EventGraph, offset: float) -> int:
    later_notes = [note.measure_number for note in graph.sorted_events() if note.offset_quarters >= offset]
    return later_notes[0] if later_notes else graph.section.measure_end


def _measure_before_offset(graph: EventGraph, offset: float) -> int:
    earlier_notes = [note.measure_number for note in graph.sorted_events() if note.offset_quarters < offset]
    return earlier_notes[-1] if earlier_notes else graph.section.measure_start


def segment_episodes(graph: EventGraph) -> list[dict[str, object]]:
    subjects = detect_subject_candidates(graph)
    if not subjects:
        return []
    subject_regions = []
    for subject in subjects:
        for occurrence in subject["occurrences"]:
            subject_regions.append((occurrence["start_onset"], occurrence["end_onset"], subject["pattern"]))
    subject_regions.sort()
    merged: list[list[object]] = []
    for start_onset, end_onset, pattern in subject_regions:
        if not merged or start_onset > merged[-1][1]:
            merged.append([start_onset, end_onset, [pattern]])
        else:
            merged[-1][1] = max(merged[-1][1], end_onset)
            merged[-1][2].append(pattern)
    episodes: list[dict[str, object]] = []
    for index, (left, right) in enumerate(zip(merged, merged[1:]), start=1):
        if right[0] <= left[1]:
            continue
        episodes.append(
            {
                "index": index,
                "type": "episode",
                "start_onset": left[1],
                "end_onset": right[0],
                "measure_start": _measure_after_offset(graph, left[1]),
                "measure_end": _measure_before_offset(graph, right[0]),
                "between_subject_patterns": left[2][-1:] + right[2][:1],
            }
        )
    return episodes
