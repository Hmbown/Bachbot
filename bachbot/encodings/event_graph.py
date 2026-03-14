from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import numpy as np
from pydantic import Field

from bachbot.models.base import BachbotModel, KeyEstimate, TypedNote
from bachbot.models.refs import MeasureRangeReference, PassageRef
from bachbot.models.section import Section
from bachbot.models.voice import Voice


class MeasureAddress(BachbotModel):
    measure_number_notated: int
    measure_number_logical: int
    onset: float
    duration: float
    voice_ids: list[str] = Field(default_factory=list)


class EncodingMetadata(BachbotModel):
    encoding_id: str
    work_id: str | None = None
    source_path: str | None = None
    title: str | None = None
    composer: str | None = None
    source_format: str = "musicxml"
    key_estimate: KeyEstimate | None = None
    meter: str | None = None
    provenance: list[str] = Field(default_factory=list)


class VerticalitySlice(BachbotModel):
    onset: float
    duration: float
    measure_number: int
    active_notes: list[TypedNote] = Field(default_factory=list)

    @property
    def pitch_classes(self) -> list[int]:
        return sorted({note.midi % 12 for note in self.active_notes if note.midi is not None and not note.is_rest})

    @property
    def bass_note(self) -> TypedNote | None:
        pitches = [note for note in self.active_notes if note.midi is not None]
        return min(pitches, key=lambda note: note.midi) if pitches else None

    @property
    def soprano_note(self) -> TypedNote | None:
        pitches = [note for note in self.active_notes if note.midi is not None]
        return max(pitches, key=lambda note: note.midi) if pitches else None


class EventGraph(BachbotModel):
    metadata: EncodingMetadata
    section: Section
    voices: list[Voice] = Field(default_factory=list)
    notes: list[TypedNote] = Field(default_factory=list)

    @property
    def work_id(self) -> str:
        return self.metadata.work_id or self.metadata.encoding_id

    @property
    def title(self) -> str:
        return self.metadata.title or self.metadata.encoding_id

    @property
    def source_path(self) -> str | None:
        return self.metadata.source_path

    @property
    def meter(self) -> str | None:
        return self.metadata.meter

    @property
    def events(self) -> list[TypedNote]:
        return self.notes

    @property
    def measures(self) -> list[MeasureAddress]:
        from bachbot.encodings.address_maps import build_measure_map

        return build_measure_map(self)

    def measure_numbers(self) -> list[int]:
        return sorted({note.measure_number for note in self.notes})

    def notes_by_voice(self) -> dict[str, list[TypedNote]]:
        bucket: dict[str, list[TypedNote]] = defaultdict(list)
        for note in self.notes:
            bucket[note.voice_id].append(note)
        return {voice_id: sorted(items, key=lambda item: (item.offset_quarters, item.midi or -1)) for voice_id, items in bucket.items()}

    def voice_events(self, voice_id: str) -> list[TypedNote]:
        return [note for note in self.notes_by_voice().get(voice_id, []) if not note.is_rest]

    def pitch_events(self) -> list[TypedNote]:
        return [note for note in sorted(self.notes, key=lambda item: (item.offset_quarters, item.voice_id)) if not note.is_rest and note.midi is not None]

    def notes_by_measure(self) -> dict[int, list[TypedNote]]:
        bucket: dict[int, list[TypedNote]] = defaultdict(list)
        for note in self.notes:
            bucket[note.measure_number].append(note)
        return {measure: sorted(items, key=lambda item: (item.offset_quarters, item.voice_id)) for measure, items in bucket.items()}

    def sorted_events(self) -> list[TypedNote]:
        return sorted(self.notes, key=lambda item: (item.offset_quarters, item.voice_id, item.midi or -1))

    def total_duration(self) -> float:
        return self.global_end_offset()

    def iter_onsets(self):
        for onset in sorted({note.offset_quarters for note in self.notes if not note.is_rest}):
            yield onset

    def active_pitches_at(self, offset_quarters: float) -> list[TypedNote]:
        return [note for note in self.active_notes_at(offset_quarters) if not note.is_rest and note.midi is not None]

    def ordered_voice_ids(self) -> list[str]:
        return [voice.voice_id for voice in self.voices] or sorted({note.voice_id for note in self.notes})

    def global_end_offset(self) -> float:
        if not self.notes:
            return 0.0
        return max(note.offset_quarters + note.duration_quarters for note in self.notes)

    def active_notes_at(self, offset_quarters: float) -> list[TypedNote]:
        active: list[TypedNote] = []
        for note in self.notes:
            if note.offset_quarters <= offset_quarters < note.offset_quarters + note.duration_quarters:
                active.append(note)
        order = self.ordered_voice_ids()
        return sorted(active, key=lambda note: (order.index(note.voice_id) if note.voice_id in order else 99, note.midi or -1))

    def passage_ref(self, measure_start: int, measure_end: int, voice_ids: list[str] | None = None) -> PassageRef:
        voices = voice_ids or sorted({note.voice_id for note in self.notes if measure_start <= note.measure_number <= measure_end})
        return PassageRef(measure_start=measure_start, measure_end=measure_end, voice_ids=voices)

    def range_references(self) -> list[MeasureRangeReference]:
        from bachbot.encodings.address_maps import build_measure_address_map

        return build_measure_address_map(self)

    def to_piano_roll(self, resolution: int = 4) -> np.ndarray:
        from bachbot.encodings.tensors import piano_roll_from_graph

        return piano_roll_from_graph(self, resolution=resolution)

    def to_voice_tensor(
        self,
        resolution: int = 4,
        pitch_range: tuple[int, int] | None = None,
        voice_order: Sequence[str] | None = None,
    ) -> np.ndarray:
        from bachbot.encodings.tensors import voice_tensor_from_graph

        return voice_tensor_from_graph(self, resolution=resolution, pitch_range=pitch_range, voice_order=voice_order)

    def to_chord_sequence(self, vocabulary: Sequence[str] | None = None) -> np.ndarray:
        from bachbot.encodings.tensors import chord_sequence_from_graph

        return chord_sequence_from_graph(self, vocabulary=vocabulary)

    def to_lilypond(self) -> str:
        from bachbot.exports.lilypond_export import event_graph_to_lilypond

        return event_graph_to_lilypond(self)

    def to_music21(self, *, include_analysis_lyrics: bool = True):
        from bachbot.integrations.music21 import event_graph_to_music21

        return event_graph_to_music21(self, include_analysis_lyrics=include_analysis_lyrics)

    @classmethod
    def from_piano_roll(
        cls,
        piano_roll: np.ndarray,
        *,
        resolution: int = 4,
        metadata: EncodingMetadata | None = None,
        work_id: str | None = None,
        encoding_id: str | None = None,
    ) -> EventGraph:
        from bachbot.encodings.tensors import event_graph_from_piano_roll

        return event_graph_from_piano_roll(
            piano_roll,
            resolution=resolution,
            metadata=metadata,
            work_id=work_id,
            encoding_id=encoding_id,
        )

    @classmethod
    def from_music21(
        cls,
        score,
        *,
        work_id: str | None = None,
        encoding_id: str | None = None,
    ) -> EventGraph:
        from bachbot.integrations.music21 import music21_to_event_graph

        return music21_to_event_graph(
            score,
            work_id=work_id,
            encoding_id=encoding_id,
        )
