"""Lightweight symbolic alignment helpers."""

from __future__ import annotations

from collections.abc import Sequence

from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import TypedNote
from bachbot.models.edition import (
    EditionNoteAddress,
    EditionNoteSnapshot,
    EditionVariant,
    VariantReport,
    VariantSummary,
    VariantType,
)
from bachbot.models.refs import PassageRef

VOICE_ALIGNMENT_GAP_COST = 1.25


def compare_measure_spans(left: EventGraph, right: EventGraph) -> dict[int, tuple[int, int]]:
    comparison: dict[int, tuple[int, int]] = {}
    left_measures = left.notes_by_measure()
    right_measures = right.notes_by_measure()
    all_measures = sorted(set(left_measures) | set(right_measures))
    for measure in all_measures:
        comparison[measure] = (len(left_measures.get(measure, [])), len(right_measures.get(measure, [])))
    return comparison


def compare_voice_spans(left: EventGraph, right: EventGraph) -> dict[str, tuple[int, int]]:
    comparison: dict[str, tuple[int, int]] = {}
    left_voices = left.notes_by_voice()
    right_voices = right.notes_by_voice()
    all_voice_ids = sorted(set(left_voices) | set(right_voices))
    for voice_id in all_voice_ids:
        comparison[voice_id] = (len(left_voices.get(voice_id, [])), len(right_voices.get(voice_id, [])))
    return comparison


def align_editions(
    left: EventGraph,
    right: EventGraph,
    *,
    left_label: str | None = None,
    right_label: str | None = None,
) -> VariantReport:
    left_voices = left.notes_by_voice()
    right_voices = right.notes_by_voice()
    variants: list[EditionVariant] = []
    unchanged_count = 0

    for voice_id in sorted(set(left_voices) | set(right_voices)):
        for left_note, right_note in _align_voice_sequences(
            left_voices.get(voice_id, []),
            right_voices.get(voice_id, []),
        ):
            if left_note and right_note:
                note_variants = _classify_shared_note_variants(left_note, right_note)
                if note_variants:
                    variants.extend(note_variants)
                else:
                    unchanged_count += 1
                continue
            if left_note:
                variants.append(
                    _build_variant(
                        left_note,
                        None,
                        variant_type=VariantType.REMOVED_NOTE,
                        detail="Note present only in left edition after voice-sequence alignment.",
                    )
                )
            if right_note:
                variants.append(
                    _build_variant(
                        None,
                        right_note,
                        variant_type=VariantType.ADDED_NOTE,
                        detail="Note present only in right edition after voice-sequence alignment.",
                    )
                )

    measure_span_comparison = compare_measure_spans(left, right)
    voice_span_comparison = compare_voice_spans(left, right)
    return VariantReport(
        left_label=left_label or left.title,
        right_label=right_label or right.title,
        left_work_id=left.work_id,
        right_work_id=right.work_id,
        measure_span_comparison=measure_span_comparison,
        voice_span_comparison=voice_span_comparison,
        variants=variants,
        summary=VariantSummary.from_variants(
            variants,
            unchanged_count=unchanged_count,
            measure_count=len(measure_span_comparison),
        ),
    )


def _align_voice_sequences(
    left_notes: Sequence[TypedNote],
    right_notes: Sequence[TypedNote],
) -> list[tuple[TypedNote | None, TypedNote | None]]:
    if not left_notes:
        return [(None, note) for note in right_notes]
    if not right_notes:
        return [(note, None) for note in left_notes]

    row_count = len(left_notes) + 1
    col_count = len(right_notes) + 1
    scores = [[0.0] * col_count for _ in range(row_count)]
    backtrack: list[list[str | None]] = [[None] * col_count for _ in range(row_count)]

    for row in range(1, row_count):
        scores[row][0] = row * VOICE_ALIGNMENT_GAP_COST
        backtrack[row][0] = "delete"
    for col in range(1, col_count):
        scores[0][col] = col * VOICE_ALIGNMENT_GAP_COST
        backtrack[0][col] = "insert"

    for row in range(1, row_count):
        for col in range(1, col_count):
            match_score = scores[row - 1][col - 1] + _note_match_cost(left_notes[row - 1], right_notes[col - 1])
            delete_score = scores[row - 1][col] + VOICE_ALIGNMENT_GAP_COST
            insert_score = scores[row][col - 1] + VOICE_ALIGNMENT_GAP_COST
            best_score = min(match_score, delete_score, insert_score)
            scores[row][col] = best_score
            if match_score <= delete_score and match_score <= insert_score:
                backtrack[row][col] = "match"
            elif delete_score <= insert_score:
                backtrack[row][col] = "delete"
            else:
                backtrack[row][col] = "insert"

    aligned: list[tuple[TypedNote | None, TypedNote | None]] = []
    row = len(left_notes)
    col = len(right_notes)
    while row > 0 or col > 0:
        step = backtrack[row][col]
        if step == "match":
            aligned.append((left_notes[row - 1], right_notes[col - 1]))
            row -= 1
            col -= 1
        elif step == "delete":
            aligned.append((left_notes[row - 1], None))
            row -= 1
        elif step == "insert":
            aligned.append((None, right_notes[col - 1]))
            col -= 1
        elif row > 0:
            aligned.append((left_notes[row - 1], None))
            row -= 1
        else:
            aligned.append((None, right_notes[col - 1]))
            col -= 1
    aligned.reverse()
    return aligned


def _note_match_cost(left: TypedNote, right: TypedNote) -> float:
    if left.is_rest != right.is_rest:
        return VOICE_ALIGNMENT_GAP_COST * 4

    if _note_address_key(left) == _note_address_key(right):
        cost = 0.0
        if _pitch_identity(left) != _pitch_identity(right):
            cost += 0.75
        if round(left.duration_quarters, 6) != round(right.duration_quarters, 6):
            cost += 0.75
        if left.accidental != right.accidental:
            cost += 0.2
        if left.lyric != right.lyric:
            cost += 0.2
        if left.tie_start != right.tie_start or left.tie_stop != right.tie_stop:
            cost += 0.15
        return cost

    cost = 0.0
    if _pitch_identity(left) != _pitch_identity(right):
        cost += 1.25
    if round(left.duration_quarters, 6) != round(right.duration_quarters, 6):
        cost += 1.0
    if left.accidental != right.accidental:
        cost += 0.4
    if left.lyric != right.lyric:
        cost += 0.4
    if left.tie_start != right.tie_start or left.tie_stop != right.tie_stop:
        cost += 0.3
    cost += min(abs(left.measure_number - right.measure_number), 4) * 0.35
    cost += min(abs(round(left.offset_quarters - right.offset_quarters, 6)), 4.0) * 0.35
    cost += min(abs(round(left.beat - right.beat, 6)), 4.0) * 0.15
    return cost


def _classify_shared_note_variants(left: TypedNote, right: TypedNote) -> list[EditionVariant]:
    variants: list[EditionVariant] = []
    rhythm_details: list[str] = []

    if _note_address_key(left) != _note_address_key(right):
        rhythm_details.append(
            f"Address changed from {_format_note_position(left)} to {_format_note_position(right)}."
        )
    if round(left.duration_quarters, 6) != round(right.duration_quarters, 6):
        rhythm_details.append(
            f"Duration changed from {left.duration_quarters} to {right.duration_quarters} quarter notes."
        )
    if rhythm_details:
        variants.append(
            _build_variant(
                left,
                right,
                variant_type=VariantType.RHYTHM,
                detail=" ".join(rhythm_details),
            )
        )

    left_pitch = _pitch_identity(left)
    right_pitch = _pitch_identity(right)
    if left_pitch != right_pitch:
        variants.append(
            _build_variant(
                left,
                right,
                variant_type=VariantType.PITCH,
                detail=f"Pitch changed from {left.pitch or left.midi} to {right.pitch or right.midi}.",
            )
        )
    if left.accidental != right.accidental:
        variants.append(
            _build_variant(
                left,
                right,
                variant_type=VariantType.ACCIDENTAL,
                detail=f"Accidental changed from {left.accidental!r} to {right.accidental!r}.",
            )
        )
    if left.lyric != right.lyric:
        variants.append(
            _build_variant(
                left,
                right,
                variant_type=VariantType.TEXT,
                detail=f"Lyric changed from {left.lyric!r} to {right.lyric!r}.",
            )
        )
    if left.tie_start != right.tie_start or left.tie_stop != right.tie_stop:
        variants.append(
            _build_variant(
                left,
                right,
                variant_type=VariantType.TIE,
                detail=(
                    "Tie flags changed from "
                    f"(start={left.tie_start}, stop={left.tie_stop}) "
                    f"to (start={right.tie_start}, stop={right.tie_stop})."
                ),
            )
        )
    return variants


def _format_note_position(note: TypedNote) -> str:
    return f"m{note.measure_number} beat {round(note.beat, 6)} onset {round(note.offset_quarters, 6)}"


def _build_variant(
    left: TypedNote | None,
    right: TypedNote | None,
    *,
    variant_type: VariantType,
    detail: str,
) -> EditionVariant:
    note = left or right
    if note is None:
        raise ValueError("A variant requires at least one note.")
    address = _note_address(note)
    return EditionVariant(
        variant_type=variant_type,
        passage_ref=PassageRef(measure_start=note.measure_number, measure_end=note.measure_number, voice_ids=[note.voice_id]),
        address=address,
        left_note=_note_snapshot(left) if left else None,
        right_note=_note_snapshot(right) if right else None,
        detail=detail,
    )


def _note_address_key(note: TypedNote) -> tuple[int, float, str]:
    return (note.measure_number, round(note.offset_quarters, 6), note.voice_id)


def _note_address(note: TypedNote) -> EditionNoteAddress:
    return EditionNoteAddress(
        measure_number=note.measure_number,
        onset=round(note.offset_quarters, 6),
        beat=round(note.beat, 6),
        voice_id=note.voice_id,
        source_ref=note.source_ref,
    )


def _note_snapshot(note: TypedNote) -> EditionNoteSnapshot:
    return EditionNoteSnapshot(
        address=_note_address(note),
        pitch=note.pitch,
        midi=note.midi,
        duration_quarters=note.duration_quarters,
        accidental=note.accidental,
        lyric=note.lyric,
        tie_start=note.tie_start,
        tie_stop=note.tie_stop,
        is_rest=note.is_rest,
    )


def _pitch_identity(note: TypedNote) -> int | str | None:
    if note.midi is not None:
        return note.midi
    return note.pitch
