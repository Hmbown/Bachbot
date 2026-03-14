from __future__ import annotations

from bachbot.analysis.counterpoint.rules import analyze_counterpoint
from bachbot.analysis.harmony.verticalities import build_verticalities
from bachbot.analysis.counterpoint.voiceleading import summarize_outer_voice_motion
from bachbot.encodings.event_graph import EventGraph

RANGES = {"soprano": (60, 81), "alto": (55, 74), "tenor": (48, 69), "bass": (36, 64)}


def _voice_role(voice_id: str) -> str:
    lowered = voice_id.lower()
    if "soprano" in lowered or lowered.startswith("s"):
        return "soprano"
    if "alto" in lowered or lowered.startswith("a"):
        return "alto"
    if "tenor" in lowered or lowered.startswith("t"):
        return "tenor"
    return "bass"


def validate_satb_ranges(graph: EventGraph) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for voice_id, notes in graph.notes_by_voice().items():
        low, high = RANGES[_voice_role(voice_id)]
        for note in notes:
            if note.midi is None or note.is_rest:
                continue
            if note.midi < low or note.midi > high:
                issues.append({"voice": voice_id, "measure": note.measure_number, "issue": "range"})
    return issues


def validate_spacing(graph: EventGraph) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    order = graph.ordered_voice_ids()
    for slice_ in build_verticalities(graph):
        by_voice = {note.voice_id: note for note in slice_.active_notes if note.midi is not None}
        for upper, lower, limit in zip(order, order[1:], [12, 12, 19]):
            if upper in by_voice and lower in by_voice:
                interval = by_voice[upper].midi - by_voice[lower].midi
                if interval > limit:
                    issues.append({"measure": slice_.measure_number, "onset": slice_.onset, "voices": f"{upper}|{lower}", "issue": "spacing", "interval": interval})
    return issues


def analyze_chorale_texture(graph: EventGraph) -> dict[str, object]:
    counterpoint = analyze_counterpoint(graph)
    range_issues = validate_satb_ranges(graph)
    spacing_issues = validate_spacing(graph)
    motion = summarize_outer_voice_motion(graph)
    return {
        "ranges_ok": not range_issues,
        "spacing_ok": not spacing_issues,
        "range_issues": range_issues,
        "spacing_issues": spacing_issues,
        "counterpoint": counterpoint,
        **motion,
    }
