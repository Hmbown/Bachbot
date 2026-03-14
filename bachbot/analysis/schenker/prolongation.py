from __future__ import annotations

from collections import defaultdict

from bachbot.models.schenker import ProlongationSpan, StructuralNote


def detect_prolongation_spans(notes: list[StructuralNote], encoding_id: str) -> list[ProlongationSpan]:
    spans: list[ProlongationSpan] = []
    by_voice: dict[str, list[StructuralNote]] = defaultdict(list)
    for note in sorted(notes, key=lambda item: (item.voice_id, item.onset, item.measure)):
        by_voice[note.voice_id].append(note)

    for voice_id, voice_notes in by_voice.items():
        spans.extend(_detect_prolongations(voice_notes, encoding_id, voice_id))
        spans.extend(_detect_linear_progressions(voice_notes, encoding_id, voice_id))

    spans.sort(key=lambda item: (item.voice_id, item.start_note_id, item.end_note_id))
    return spans


def summarize_prolongation(notes: list[StructuralNote], encoding_id: str) -> list[dict[str, object]]:
    return [span.model_dump(mode="json") for span in detect_prolongation_spans(notes, encoding_id)]


def _detect_prolongations(
    notes: list[StructuralNote],
    encoding_id: str,
    voice_id: str,
) -> list[ProlongationSpan]:
    spans: list[ProlongationSpan] = []
    for left, right in zip(notes, notes[1:]):
        same_degree = left.scale_degree is not None and left.scale_degree == right.scale_degree
        same_harmony = left.harmony_label is not None and left.harmony_label == right.harmony_label
        if not (same_degree or same_harmony):
            continue
        degrees = [degree for degree in (left.scale_degree, right.scale_degree) if degree is not None]
        spans.append(
            ProlongationSpan(
                span_id=f"{encoding_id}:span:{voice_id}:pro:{len(spans)}",
                voice_id=voice_id,
                start_note_id=left.note_id,
                end_note_id=right.note_id,
                span_type="prolongation",
                scale_degrees=degrees,
                harmony_label=right.harmony_label or left.harmony_label,
            )
        )
    return spans


def _detect_linear_progressions(
    notes: list[StructuralNote],
    encoding_id: str,
    voice_id: str,
) -> list[ProlongationSpan]:
    spans: list[ProlongationSpan] = []
    start = 0
    while start + 2 < len(notes):
        run = [notes[start]]
        direction = 0
        idx = start + 1
        while idx < len(notes):
            prev = run[-1]
            current = notes[idx]
            if prev.scale_degree is None or current.scale_degree is None:
                break
            diff = current.scale_degree - prev.scale_degree
            if abs(diff) != 1:
                break
            step_direction = 1 if diff > 0 else -1
            if direction == 0:
                direction = step_direction
            if step_direction != direction:
                break
            run.append(current)
            idx += 1
        if len(run) >= 3:
            spans.append(
                ProlongationSpan(
                    span_id=f"{encoding_id}:span:{voice_id}:zug:{len(spans)}",
                    voice_id=voice_id,
                    start_note_id=run[0].note_id,
                    end_note_id=run[-1].note_id,
                    span_type="zug",
                    scale_degrees=[note.scale_degree for note in run if note.scale_degree is not None],
                    harmony_label=run[-1].harmony_label,
                )
            )
            start = idx - 1
        else:
            start += 1
    return spans
