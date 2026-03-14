from __future__ import annotations

from bachbot.analysis.fugue.subject import detect_subject_candidates
from bachbot.encodings.event_graph import EventGraph


def scan_stretto_windows(graph: EventGraph) -> list[dict[str, object]]:
    candidates = detect_subject_candidates(graph)
    findings: list[dict[str, object]] = []
    for candidate in candidates:
        occurrences = candidate["occurrences"]
        for left_index, left in enumerate(occurrences):
            for right in occurrences[left_index + 1 :]:
                if left["voice_id"] == right["voice_id"]:
                    continue
                if right["start_onset"] >= left["end_onset"]:
                    continue
                overlap_duration = min(left["end_onset"], right["end_onset"]) - right["start_onset"]
                if overlap_duration <= 0:
                    continue
                findings.append(
                    {
                        "pattern": candidate["pattern"],
                        "voices": [left["voice_id"], right["voice_id"]],
                        "entry_gap": round(right["start_onset"] - left["start_onset"], 3),
                        "overlap_duration": round(overlap_duration, 3),
                        "window": {
                            "start_onset": left["start_onset"],
                            "end_onset": max(left["end_onset"], right["end_onset"]),
                            "start_measure": min(left["start_measure"], right["start_measure"]),
                            "end_measure": max(left["end_measure"], right["end_measure"]),
                        },
                    }
                )
    return findings
