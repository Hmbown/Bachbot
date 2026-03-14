from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph, MeasureAddress
from bachbot.models.refs import MeasureRangeReference


def build_measure_map(graph: EventGraph) -> list[MeasureAddress]:
    result: list[MeasureAddress] = []
    for measure_number in graph.measure_numbers():
        notes = graph.notes_by_measure()[measure_number]
        onset = min(note.offset_quarters for note in notes)
        end = max(note.offset_quarters + note.duration_quarters for note in notes)
        result.append(
            MeasureAddress(
                measure_number_notated=measure_number,
                measure_number_logical=measure_number,
                onset=onset,
                duration=end - onset,
                voice_ids=sorted({note.voice_id for note in notes}),
            )
        )
    return result


def build_measure_address_map(graph: EventGraph) -> list[MeasureRangeReference]:
    return [
        MeasureRangeReference(
            ref_id=f"{graph.section.section_id}:m{measure.measure_number_logical}",
            work_id=graph.work_id,
            section_id=graph.section.section_id,
            source_or_encoding_id=graph.metadata.encoding_id,
            measure_number_notated=measure.measure_number_notated,
            measure_number_logical=measure.measure_number_logical,
            beat_start=1.0,
            beat_end=measure.duration,
            voice_ids=measure.voice_ids,
        )
        for measure in build_measure_map(graph)
    ]


def address_for_measure(graph: EventGraph, measure_number: int) -> MeasureRangeReference:
    for ref in build_measure_address_map(graph):
        if ref.measure_number_logical == measure_number:
            return ref
    raise KeyError(measure_number)
