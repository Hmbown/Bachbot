from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph, VerticalitySlice


def build_verticalities(graph: EventGraph) -> list[VerticalitySlice]:
    onsets = sorted({note.offset_quarters for note in graph.notes if not note.is_rest})
    end_offset = graph.global_end_offset()
    slices: list[VerticalitySlice] = []
    for index, onset in enumerate(onsets):
        next_onset = onsets[index + 1] if index + 1 < len(onsets) else end_offset
        active = graph.active_notes_at(onset)
        if not active:
            continue
        onset_notes = [note for note in active if note.offset_quarters == onset]
        slices.append(
            VerticalitySlice(
                onset=onset,
                duration=max(0.25, next_onset - onset),
                measure_number=min(note.measure_number for note in (onset_notes or active)),
                active_notes=active,
            )
        )
    return slices
