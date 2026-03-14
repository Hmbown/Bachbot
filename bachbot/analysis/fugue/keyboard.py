"""Keyboard normalization helpers for fugue analysis.

Provides voice separation for 2-staff keyboard music (e.g., WTC fugues)
using pitch-proximity heuristics.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import TypedNote


def separate_voices_by_pitch(
    notes: list[TypedNote],
    *,
    max_voices: int = 3,
) -> dict[str, list[TypedNote]]:
    """Separate a flat stream of notes into voices by pitch proximity.

    At each onset, notes are assigned to voices minimising total pitch
    distance from the previous assignment.  Handles voice crossing by
    preferring proximity over fixed ordering.

    Returns a dict mapping generated voice IDs (``"V1"``, ``"V2"``, ...)
    to sorted note lists.
    """
    if not notes or max_voices < 1:
        return {}

    # Group notes by onset.
    by_onset: dict[float, list[TypedNote]] = defaultdict(list)
    for note in notes:
        if note.midi is not None and not note.is_rest:
            by_onset[note.offset_quarters].append(note)

    onsets = sorted(by_onset)
    if not onsets:
        return {}

    # Determine effective voice count from the maximum simultaneous notes,
    # capped by *max_voices*.
    n_voices = min(max(len(by_onset[o]) for o in onsets), max_voices)

    # Track the last-assigned MIDI pitch for each voice slot.
    last_pitch: list[int | None] = [None] * n_voices
    result: dict[str, list[TypedNote]] = {f"V{i + 1}": [] for i in range(n_voices)}

    for onset in onsets:
        candidates = sorted(by_onset[onset], key=lambda n: n.midi)  # type: ignore[arg-type]
        # Trim to max_voices; keep outermost pitches when there are extras.
        if len(candidates) > n_voices:
            candidates = candidates[:n_voices]

        assigned: list[TypedNote | None] = [None] * n_voices
        used_candidates: set[int] = set()

        # Greedy assignment: build cost matrix, pick minimum cost pairs.
        costs: list[tuple[float, int, int]] = []
        for vi in range(n_voices):
            for ci, cand in enumerate(candidates):
                if last_pitch[vi] is None:
                    cost = 0.0
                else:
                    cost = abs(cand.midi - last_pitch[vi])  # type: ignore[operator]
                costs.append((cost, vi, ci))
        costs.sort()

        used_voices: set[int] = set()
        for cost, vi, ci in costs:
            if vi in used_voices or ci in used_candidates:
                continue
            assigned[vi] = candidates[ci]
            used_candidates.add(ci)
            used_voices.add(vi)
            if len(used_voices) == min(n_voices, len(candidates)):
                break

        # Assign any remaining candidates to the first free voice slot.
        for ci, cand in enumerate(candidates):
            if ci not in used_candidates:
                for vi in range(n_voices):
                    if vi not in used_voices:
                        assigned[vi] = cand
                        used_voices.add(vi)
                        break

        for vi in range(n_voices):
            note = assigned[vi]
            if note is not None:
                voice_id = f"V{vi + 1}"
                new_note = note.model_copy(update={"voice_id": voice_id})
                result[voice_id].append(new_note)
                last_pitch[vi] = note.midi

    # Sort each voice by onset.
    for voice_id in result:
        result[voice_id].sort(key=lambda n: (n.offset_quarters, n.midi or -1))

    return result


def normalize_keyboard_staves(graph: EventGraph) -> EventGraph:
    """Reassign voice IDs for 2-staff keyboard music.

    For each staff, runs pitch-proximity voice separation and relabels
    the notes.  Returns a new :class:`EventGraph` with voice-separated
    notes.
    """
    # Group notes by staff_id.
    by_staff: dict[str | None, list[TypedNote]] = defaultdict(list)
    for note in graph.notes:
        by_staff[note.staff_id].append(note)

    staff_ids = sorted(by_staff.keys(), key=lambda s: s or "")

    # If there's only one staff (or none), separate all notes together.
    if len(staff_ids) <= 1:
        separated = separate_voices_by_pitch(graph.notes, max_voices=4)
        all_notes = [note for voice_notes in separated.values() for note in voice_notes]
    else:
        all_notes: list[TypedNote] = []
        voice_offset = 0
        for staff_id in staff_ids:
            staff_notes = by_staff[staff_id]
            separated = separate_voices_by_pitch(staff_notes, max_voices=3)
            for vid, vnotes in separated.items():
                # Re-label with globally unique voice IDs.
                idx = int(vid[1:]) + voice_offset
                relabeled_id = f"V{idx}"
                for note in vnotes:
                    all_notes.append(note.model_copy(update={"voice_id": relabeled_id}))
            voice_offset += len(separated)

    all_notes.sort(key=lambda n: (n.offset_quarters, n.voice_id, n.midi or -1))

    new_graph = graph.model_copy(
        update={
            "notes": all_notes,
            "voices": [],  # voices will be inferred from notes
        }
    )
    return new_graph
