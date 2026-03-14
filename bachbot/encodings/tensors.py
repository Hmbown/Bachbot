from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import ceil

import numpy as np

from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.encodings.musicxml_io import midi_to_note_name
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice


def _validate_resolution(resolution: int) -> None:
    if resolution <= 0:
        raise ValueError("resolution must be positive")


def _graph_steps(graph: EventGraph, resolution: int) -> int:
    duration = graph.total_duration()
    if duration <= 0:
        return 1
    return max(1, int(ceil(duration * resolution)))


def _step_span(note: TypedNote, resolution: int) -> tuple[int, int]:
    start = int(round(note.offset_quarters * resolution))
    end = int(round((note.offset_quarters + note.duration_quarters) * resolution))
    if end <= start:
        end = start + 1
    return start, end


def piano_roll_from_graph(graph: EventGraph, *, resolution: int = 4) -> np.ndarray:
    _validate_resolution(resolution)
    piano_roll = np.zeros((_graph_steps(graph, resolution), 128), dtype=np.float32)
    for note in graph.notes:
        if note.is_rest or note.midi is None:
            continue
        start, end = _step_span(note, resolution)
        piano_roll[start:end, note.midi] = 1.0
    return piano_roll


def _resolve_pitch_range(graph: EventGraph, pitch_range: tuple[int, int] | None) -> tuple[int, int]:
    if pitch_range is not None:
        low, high = pitch_range
    else:
        midis = [note.midi for note in graph.notes if note.midi is not None and not note.is_rest]
        low = min(midis, default=0)
        high = max(midis, default=127)
    if low > high:
        raise ValueError("pitch_range must be ordered as (low, high)")
    return low, high


def voice_tensor_from_graph(
    graph: EventGraph,
    *,
    resolution: int = 4,
    pitch_range: tuple[int, int] | None = None,
    voice_order: Sequence[str] | None = None,
) -> np.ndarray:
    _validate_resolution(resolution)
    low, high = _resolve_pitch_range(graph, pitch_range)
    ordered_voices = list(voice_order or graph.ordered_voice_ids())
    voice_index = {voice_id: index for index, voice_id in enumerate(ordered_voices)}
    tensor = np.zeros((_graph_steps(graph, resolution), len(ordered_voices), (high - low) + 1), dtype=np.float32)
    for note in graph.notes:
        if note.is_rest or note.midi is None or note.voice_id not in voice_index:
            continue
        if note.midi < low or note.midi > high:
            continue
        start, end = _step_span(note, resolution)
        tensor[start:end, voice_index[note.voice_id], note.midi - low] = 1.0
    return tensor


def chord_token_sequence_from_graph(graph: EventGraph) -> list[str]:
    tokens: list[str] = []
    for onset in graph.iter_onsets():
        pitch_classes = sorted({note.midi % 12 for note in graph.active_pitches_at(onset)})
        if not pitch_classes:
            continue
        tokens.append("-".join(str(pc) for pc in pitch_classes))
    return tokens or ["silence"]


def build_chord_vocabulary(graphs: Iterable[EventGraph]) -> list[str]:
    vocabulary = sorted({token for graph in graphs for token in chord_token_sequence_from_graph(graph)})
    return vocabulary or ["silence"]


def chord_sequence_from_graph(graph: EventGraph, *, vocabulary: Sequence[str] | None = None) -> np.ndarray:
    tokens = chord_token_sequence_from_graph(graph)
    ordered_vocabulary = list(vocabulary or sorted(set(tokens)))
    token_index = {token: index for index, token in enumerate(ordered_vocabulary)}
    sequence = np.zeros((len(tokens), len(ordered_vocabulary)), dtype=np.float32)
    for row, token in enumerate(tokens):
        sequence[row, token_index[token]] = 1.0
    return sequence


def _measure_length(meter: str | None) -> float:
    if not meter or "/" not in meter:
        return 4.0
    beats_text, beat_type_text = meter.split("/", 1)
    beats = int(beats_text)
    beat_type = int(beat_type_text)
    return beats * (4.0 / beat_type)


def _measure_number(offset_quarters: float, meter: str | None) -> int:
    measure_length = _measure_length(meter)
    return int(offset_quarters // measure_length) + 1


def _beat_number(offset_quarters: float, meter: str | None) -> float:
    measure_length = _measure_length(meter)
    return (offset_quarters % measure_length) + 1.0


def event_graph_from_piano_roll(
    piano_roll: np.ndarray,
    *,
    resolution: int = 4,
    metadata: EncodingMetadata | None = None,
    work_id: str | None = None,
    encoding_id: str | None = None,
) -> EventGraph:
    _validate_resolution(resolution)
    matrix = np.asarray(piano_roll)
    if matrix.ndim != 2 or matrix.shape[1] != 128:
        raise ValueError("piano_roll must have shape (time_steps, 128)")

    restored_metadata = metadata.model_copy(deep=True) if metadata is not None else EncodingMetadata(
        encoding_id=encoding_id or "piano-roll",
        work_id=work_id or encoding_id or "piano-roll",
        source_format="piano_roll",
        key_estimate=KeyEstimate(tonic="C", mode="major", confidence=0.0),
    )
    restored_metadata.source_format = "piano_roll"
    if encoding_id is not None:
        restored_metadata.encoding_id = encoding_id
    if work_id is not None:
        restored_metadata.work_id = work_id
    if restored_metadata.work_id is None:
        restored_metadata.work_id = restored_metadata.encoding_id
    if restored_metadata.key_estimate is None:
        restored_metadata.key_estimate = KeyEstimate(tonic="C", mode="major", confidence=0.0)

    section = Section(
        section_id="tensor_section",
        work_id=restored_metadata.work_id,
        label="Tensor import",
        section_type="tensor_import",
        measure_start=1,
        measure_end=1,
    )
    voices: dict[str, Voice] = {}
    notes: list[TypedNote] = []

    for midi in range(matrix.shape[1]):
        is_active = matrix[:, midi] > 0
        note_start: int | None = None
        for step in range(matrix.shape[0] + 1):
            active = bool(is_active[step]) if step < matrix.shape[0] else False
            if active and note_start is None:
                note_start = step
                continue
            if active or note_start is None:
                continue
            offset = note_start / resolution
            duration = (step - note_start) / resolution
            measure_number = _measure_number(offset, restored_metadata.meter)
            voice_id = f"PR:{midi}"
            if voice_id not in voices:
                voices[voice_id] = Voice(
                    voice_id=voice_id,
                    section_id=section.section_id,
                    part_name="piano_roll",
                    normalized_voice_name=voice_id,
                    instrument_or_role="piano_roll",
                    range_profile=(midi, midi),
                )
            notes.append(
                TypedNote(
                    pitch=midi_to_note_name(midi),
                    midi=midi,
                    duration_quarters=duration,
                    offset_quarters=offset,
                    measure_number=measure_number,
                    beat=_beat_number(offset, restored_metadata.meter),
                    voice_id=voice_id,
                    part_name="piano_roll",
                    source_ref=f"tensor:m{measure_number}:{note_start}",
                )
            )
            note_start = None

    if notes:
        section.measure_end = max(note.measure_number for note in notes)

    return EventGraph(metadata=restored_metadata, section=section, voices=list(voices.values()), notes=notes)
