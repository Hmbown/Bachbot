from __future__ import annotations

from itertools import combinations

from bachbot.analysis.harmony.verticalities import build_verticalities
from bachbot.encodings.event_graph import EventGraph

PERFECT_INTERVALS = {0, 7}


def _motion(a1: int, a2: int) -> int:
    if a2 > a1:
        return 1
    if a2 < a1:
        return -1
    return 0


def detect_parallels(graph: EventGraph) -> list[dict[str, str | int | float]]:
    findings: list[dict[str, str | int | float]] = []
    slices = build_verticalities(graph)
    for left, right in zip(slices, slices[1:]):
        left_notes = {note.voice_id: note for note in left.active_notes if note.midi is not None}
        right_notes = {note.voice_id: note for note in right.active_notes if note.midi is not None}
        shared = sorted(set(left_notes) & set(right_notes))
        for a, b in combinations(shared, 2):
            left_interval = abs(left_notes[b].midi - left_notes[a].midi) % 12
            right_interval = abs(right_notes[b].midi - right_notes[a].midi) % 12
            move_a = _motion(left_notes[a].midi, right_notes[a].midi)
            move_b = _motion(left_notes[b].midi, right_notes[b].midi)
            if left_interval in PERFECT_INTERVALS and right_interval in PERFECT_INTERVALS and move_a == move_b != 0:
                if left_interval == right_interval:
                    findings.append({"type": "parallel_8ves" if right_interval == 0 else "parallel_5ths", "voices": f"{a}|{b}", "measure": right.measure_number, "onset": right.onset})
                else:
                    findings.append(
                        {
                            "type": "direct_perfect",
                            "voices": f"{a}|{b}",
                            "measure": right.measure_number,
                            "onset": right.onset,
                            "from_interval": left_interval,
                            "to_interval": right_interval,
                        }
                    )
    return findings


def detect_voice_crossings(graph: EventGraph) -> list[dict[str, str | int | float]]:
    findings: list[dict[str, str | int | float]] = []
    order = graph.ordered_voice_ids()
    for slice_ in build_verticalities(graph):
        by_voice = {note.voice_id: note.midi for note in slice_.active_notes if note.midi is not None}
        for upper, lower in zip(order, order[1:]):
            if upper in by_voice and lower in by_voice and by_voice[upper] < by_voice[lower]:
                findings.append({"type": "voice_crossing", "voices": f"{upper}|{lower}", "measure": slice_.measure_number, "onset": slice_.onset})
    return findings


def summarize_outer_voice_motion(graph: EventGraph) -> dict[str, int]:
    summary = {"similar": 0, "contrary": 0, "oblique": 0, "parallel": 0}
    slices = build_verticalities(graph)
    for left, right in zip(slices, slices[1:]):
        left_bass = left.bass_note
        left_soprano = left.soprano_note
        right_bass = right.bass_note
        right_soprano = right.soprano_note
        if not left_bass or not left_soprano or not right_bass or not right_soprano:
            continue
        bass_motion = _motion(left_bass.midi or 0, right_bass.midi or 0)
        soprano_motion = _motion(left_soprano.midi or 0, right_soprano.midi or 0)
        if bass_motion == soprano_motion == 0:
            summary["oblique"] += 1
        elif bass_motion == 0 or soprano_motion == 0:
            summary["oblique"] += 1
        elif bass_motion == soprano_motion:
            summary["similar"] += 1
            left_interval = abs((left_soprano.midi or 0) - (left_bass.midi or 0)) % 12
            right_interval = abs((right_soprano.midi or 0) - (right_bass.midi or 0)) % 12
            if left_interval == right_interval:
                summary["parallel"] += 1
        else:
            summary["contrary"] += 1
    return summary
