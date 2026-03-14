from __future__ import annotations

import importlib.util
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.encodings.musicxml_io import midi_to_note_name, note_name_to_midi
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice


class Music21UnavailableError(RuntimeError):
    """Raised when the optional music21 dependency is not installed."""


def music21_available() -> bool:
    return importlib.util.find_spec("music21") is not None


def _ensure_music21_importable() -> None:
    if not music21_available():
        raise Music21UnavailableError(
            "music21 is not installed. Install the optional dependency with `pip install bachbot[music21]`."
        )


def event_graph_to_music21(graph: EventGraph, *, include_analysis_lyrics: bool = True) -> Any:
    """Project an EventGraph into a music21 Score."""

    _ensure_music21_importable()

    from music21 import key as m21key
    from music21 import metadata as m21metadata
    from music21 import meter as m21meter
    from music21 import note as m21note
    from music21 import stream as m21stream
    from music21 import tie as m21tie

    score = m21stream.Score(id=graph.work_id)
    score.metadata = m21metadata.Metadata(title=graph.title, composer=graph.metadata.composer)
    score_misc = _misc(score)
    score_misc["bachbot_work_id"] = graph.work_id
    score_misc["bachbot_encoding_id"] = graph.metadata.encoding_id
    score_misc["bachbot_source_format"] = graph.metadata.source_format
    score_misc["bachbot_section_id"] = graph.section.section_id
    score_misc["bachbot_section_label"] = graph.section.label
    score_misc["bachbot_section_type"] = graph.section.section_type
    score_misc["bachbot_section_measure_start"] = graph.section.measure_start
    score_misc["bachbot_section_measure_end"] = graph.section.measure_end
    if graph.meter:
        score_misc["bachbot_meter"] = graph.meter
    if graph.metadata.key_estimate is not None:
        score_misc["bachbot_key_estimate_tonic"] = graph.metadata.key_estimate.tonic
        score_misc["bachbot_key_estimate_mode"] = graph.metadata.key_estimate.mode
        score_misc["bachbot_key_estimate_confidence"] = graph.metadata.key_estimate.confidence

    measure_offsets = {measure.measure_number_logical: float(measure.onset) for measure in graph.measures}
    if not measure_offsets:
        measure_offsets = {
            measure_number: _fallback_measure_offset(graph=graph, measure_number=measure_number)
            for measure_number in range(graph.section.measure_start, graph.section.measure_end + 1)
        }

    annotation_targets: dict[str, list[tuple[float, Any]]] = defaultdict(list)

    for voice_id in graph.ordered_voice_ids():
        part = m21stream.Part(id=voice_id)
        voice = next((item for item in graph.voices if item.voice_id == voice_id), None)
        part.partName = (voice.part_name if voice and voice.part_name else voice_id)
        part_misc = _misc(part)
        part_misc["bachbot_voice_id"] = voice_id
        part_misc["bachbot_part_name"] = part.partName
        part_misc["bachbot_normalized_voice_name"] = (
            voice.normalized_voice_name if voice else voice_id
        )
        part_misc["bachbot_instrument_or_role"] = (
            voice.instrument_or_role if voice and voice.instrument_or_role else part.partName
        )
        if voice and voice.staff_id is not None:
            part_misc["bachbot_staff_id"] = voice.staff_id

        by_measure: dict[int, list[tuple[float, Any]]] = defaultdict(list)
        for note in graph.notes_by_voice().get(voice_id, []):
            measure_offset = measure_offsets.get(note.measure_number)
            if measure_offset is None:
                measure_offset = _fallback_measure_offset(graph=graph, measure_number=note.measure_number)
            local_offset = round(note.offset_quarters - measure_offset, 6)
            element = _note_to_music21_element(
                note=note,
                note_cls=m21note.Note,
                rest_cls=m21note.Rest,
                tie_cls=m21tie.Tie,
            )
            by_measure[note.measure_number].append((local_offset, element))
            if not note.is_rest and note.midi is not None:
                annotation_targets[voice_id].append((float(note.offset_quarters), element))

        for measure_number in range(graph.section.measure_start, graph.section.measure_end + 1):
            measure = m21stream.Measure(number=measure_number)
            if measure_number == graph.section.measure_start:
                if graph.meter:
                    measure.insert(0.0, m21meter.TimeSignature(graph.meter))
                if graph.metadata.key_estimate is not None:
                    measure.insert(0.0, m21key.Key(graph.metadata.key_estimate.tonic, graph.metadata.key_estimate.mode))
            for local_offset, element in sorted(by_measure.get(measure_number, []), key=lambda item: item[0]):
                measure.insert(local_offset, element)
            part.insert(measure_offsets.get(measure_number, 0.0), measure)

        score.insert(0.0, part)

    if include_analysis_lyrics:
        _attach_analysis_lyrics(graph=graph, annotation_targets=annotation_targets)

    return score


def music21_to_event_graph(
    score: Any,
    *,
    work_id: str | None = None,
    encoding_id: str | None = None,
) -> EventGraph:
    """Project a music21 Score into an EventGraph."""

    _ensure_music21_importable()

    from music21 import chord as m21chord

    score_misc = _misc(score)
    resolved_work_id = (
        work_id
        or _maybe_str(score_misc.get("bachbot_work_id"))
        or getattr(score, "id", None)
        or "music21-score"
    )
    resolved_encoding_id = (
        encoding_id
        or _maybe_str(score_misc.get("bachbot_encoding_id"))
        or resolved_work_id
    )

    existing_voice_ids: set[str] = set()
    voices: list[Voice] = []
    notes: list[TypedNote] = []

    parts = list(getattr(score, "parts", [])) or [score]
    for index, part in enumerate(parts, start=1):
        part_misc = _misc(part)
        voice_id = _resolve_voice_id(part=part, part_misc=part_misc, index=index, existing=existing_voice_ids)
        existing_voice_ids.add(voice_id)
        voices.append(
            Voice(
                voice_id=voice_id,
                section_id=_maybe_str(score_misc.get("bachbot_section_id")) or "section_1",
                staff_id=_maybe_str(part_misc.get("bachbot_staff_id")),
                part_name=_maybe_str(part_misc.get("bachbot_part_name")) or getattr(part, "partName", None) or voice_id,
                normalized_voice_name=(
                    _maybe_str(part_misc.get("bachbot_normalized_voice_name"))
                    or getattr(part, "partName", None)
                    or voice_id
                ),
                instrument_or_role=(
                    _maybe_str(part_misc.get("bachbot_instrument_or_role"))
                    or getattr(part, "partName", None)
                    or voice_id
                ),
            )
        )

        for element in part.recurse().notesAndRests:
            if isinstance(element, m21chord.Chord):
                raise ValueError("music21 chords are not supported for EventGraph import; provide monophonic parts")

            element_misc = _misc(element)
            pitch_name = None
            midi = None
            is_rest = bool(element.isRest)
            if not is_rest:
                midi = int(element.pitch.midi)
                pitch_name = _maybe_str(element_misc.get("bachbot_pitch")) or midi_to_note_name(midi)

            tie_start, tie_stop = _tie_flags(element=element, element_misc=element_misc)
            articulations = tuple(_coerce_str_list(element_misc.get("bachbot_articulations")))
            absolute_offset = float(element.getOffsetInHierarchy(part))
            measure_number = int(
                element_misc.get("bachbot_measure_number")
                or getattr(element, "measureNumber", None)
                or 1
            )
            beat = float(element_misc.get("bachbot_beat") or getattr(element, "beat", 1.0))
            notes.append(
                TypedNote(
                    pitch=pitch_name,
                    midi=midi,
                    duration_quarters=float(element.quarterLength),
                    offset_quarters=absolute_offset,
                    measure_number=measure_number,
                    beat=beat,
                    voice_id=voice_id,
                    staff_id=_maybe_str(element_misc.get("bachbot_staff_id")) or _maybe_str(part_misc.get("bachbot_staff_id")),
                    part_name=_maybe_str(part_misc.get("bachbot_part_name")) or getattr(part, "partName", None) or voice_id,
                    tie_start=tie_start,
                    tie_stop=tie_stop,
                    is_rest=is_rest,
                    accidental=_maybe_str(element_misc.get("bachbot_accidental")),
                    lyric=_maybe_str(element_misc.get("bachbot_lyric")) or getattr(element, "lyric", None),
                    fermata=bool(element_misc.get("bachbot_fermata", False)),
                    articulations=list(articulations),
                    source_ref=_maybe_str(element_misc.get("bachbot_source_ref")) or f"section_1:m{measure_number}",
                )
            )

    measure_numbers = [note.measure_number for note in notes] or [1]
    section_id = _maybe_str(score_misc.get("bachbot_section_id")) or "section_1"
    section = Section(
        section_id=section_id,
        work_id=resolved_work_id,
        label=_maybe_str(score_misc.get("bachbot_section_label")) or "Imported score",
        section_type=_maybe_str(score_misc.get("bachbot_section_type")) or "movement",
        measure_start=min(measure_numbers),
        measure_end=max(measure_numbers),
    )

    metadata = EncodingMetadata(
        encoding_id=resolved_encoding_id,
        work_id=resolved_work_id,
        title=_score_title(score) or resolved_work_id,
        composer=_score_composer(score),
        source_format="music21",
        key_estimate=_score_key_estimate(score=score, score_misc=score_misc),
        meter=_score_meter(score=score, score_misc=score_misc),
        provenance=[f"Imported from music21 score {resolved_work_id}"],
    )
    if _maybe_str(score_misc.get("bachbot_source_format")):
        metadata.source_format = _maybe_str(score_misc.get("bachbot_source_format")) or metadata.source_format

    return EventGraph(metadata=metadata, section=section, voices=voices, notes=notes)


def _attach_analysis_lyrics(*, graph: EventGraph, annotation_targets: dict[str, list[tuple[float, Any]]]) -> None:
    from bachbot.analysis import analyze_graph

    if not annotation_targets:
        return

    report = analyze_graph(graph)
    preferred_voice = "S" if "S" in annotation_targets else graph.ordered_voice_ids()[0]
    targets = sorted(annotation_targets.get(preferred_voice, []), key=lambda item: item[0])
    if not targets:
        return

    first_in_measure: dict[int, Any] = {}
    for _, element in targets:
        measure_number = int(_misc(element).get("bachbot_measure_number", 1))
        first_in_measure.setdefault(measure_number, element)

    for event in report.harmony:
        if not event.roman_numeral_candidate_set:
            continue
        element = _first_target_at_or_after(targets, float(event.onset))
        if element is None:
            continue
        element.addLyric(f"RN:{event.roman_numeral_candidate_set[0]}")

    for cadence in report.cadences:
        measure_number = _measure_number_from_ref(cadence.ref_id)
        if measure_number is None:
            continue
        element = first_in_measure.get(measure_number)
        if element is not None:
            element.addLyric(f"Cadence:{cadence.cadence_type}")


def _first_target_at_or_after(targets: list[tuple[float, Any]], onset: float) -> Any | None:
    for target_onset, element in targets:
        if target_onset + 1e-6 >= onset:
            return element
    return targets[-1][1] if targets else None


def _note_to_music21_element(*, note: TypedNote, note_cls: Any, rest_cls: Any, tie_cls: Any) -> Any:
    if note.is_rest or note.midi is None:
        element = rest_cls(quarterLength=note.duration_quarters)
    else:
        pitch_name = note.pitch or midi_to_note_name(note.midi)
        element = note_cls(pitch_name, quarterLength=note.duration_quarters)
        if note.tie_start and note.tie_stop:
            element.tie = tie_cls("continue")
        elif note.tie_start:
            element.tie = tie_cls("start")
        elif note.tie_stop:
            element.tie = tie_cls("stop")
        if note.lyric:
            element.lyric = note.lyric
    misc = _misc(element)
    misc["bachbot_pitch"] = note.pitch
    misc["bachbot_midi"] = note.midi
    misc["bachbot_measure_number"] = note.measure_number
    misc["bachbot_beat"] = note.beat
    misc["bachbot_offset_quarters"] = note.offset_quarters
    misc["bachbot_duration_quarters"] = note.duration_quarters
    misc["bachbot_voice_id"] = note.voice_id
    misc["bachbot_staff_id"] = note.staff_id
    misc["bachbot_part_name"] = note.part_name
    misc["bachbot_source_ref"] = note.source_ref
    misc["bachbot_lyric"] = note.lyric
    misc["bachbot_fermata"] = note.fermata
    misc["bachbot_accidental"] = note.accidental
    misc["bachbot_tie_start"] = note.tie_start
    misc["bachbot_tie_stop"] = note.tie_stop
    misc["bachbot_articulations"] = tuple(note.articulations)
    return element


def _score_title(score: Any) -> str | None:
    metadata = getattr(score, "metadata", None)
    if metadata is None:
        return None
    return getattr(metadata, "title", None) or getattr(metadata, "movementName", None)


def _score_composer(score: Any) -> str | None:
    metadata = getattr(score, "metadata", None)
    return None if metadata is None else getattr(metadata, "composer", None)


def _score_key_estimate(*, score: Any, score_misc: dict[str, Any]) -> KeyEstimate | None:
    tonic = _maybe_str(score_misc.get("bachbot_key_estimate_tonic"))
    mode = _maybe_str(score_misc.get("bachbot_key_estimate_mode"))
    if tonic and mode:
        confidence = float(score_misc.get("bachbot_key_estimate_confidence", 0.5))
        return KeyEstimate(tonic=tonic, mode=mode, confidence=confidence)

    key_element = next((item for item in score.recurse().getElementsByClass("Key")), None)
    if key_element is None:
        return None
    return KeyEstimate(
        tonic=_normalize_tonic_name(key_element.tonic.name),
        mode=str(key_element.mode),
        confidence=0.5,
    )


def _score_meter(*, score: Any, score_misc: dict[str, Any]) -> str | None:
    meter = _maybe_str(score_misc.get("bachbot_meter"))
    if meter:
        return meter
    time_signature = next((item for item in score.recurse().getElementsByClass("TimeSignature")), None)
    return None if time_signature is None else str(time_signature.ratioString)


def _resolve_voice_id(*, part: Any, part_misc: dict[str, Any], index: int, existing: set[str]) -> str:
    candidate = (
        _maybe_str(part_misc.get("bachbot_voice_id"))
        or _maybe_str(getattr(part, "id", None))
        or _maybe_str(getattr(part, "partName", None))
        or f"V{index}"
    )
    candidate = _normalize_voice_id(candidate)
    if candidate not in existing:
        return candidate
    suffix = 2
    while f"{candidate}:{suffix}" in existing:
        suffix += 1
    return f"{candidate}:{suffix}"


def _normalize_voice_id(raw: str) -> str:
    normalized = raw.strip()
    if not normalized:
        return "V1"
    lookup = {
        "soprano": "S",
        "alto": "A",
        "tenor": "T",
        "bass": "B",
    }
    return lookup.get(normalized.lower(), normalized)


def _normalize_tonic_name(name: str) -> str:
    return name.replace("-", "b")


def _tie_flags(*, element: Any, element_misc: dict[str, Any]) -> tuple[bool, bool]:
    if "bachbot_tie_start" in element_misc or "bachbot_tie_stop" in element_misc:
        return bool(element_misc.get("bachbot_tie_start", False)), bool(element_misc.get("bachbot_tie_stop", False))

    tie = getattr(element, "tie", None)
    if tie is None:
        return False, False
    if tie.type == "start":
        return True, False
    if tie.type == "stop":
        return False, True
    if tie.type == "continue":
        return True, True
    return False, False


def _coerce_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


def _fallback_measure_offset(*, graph: EventGraph, measure_number: int) -> float:
    return max(0.0, (measure_number - graph.section.measure_start) * _measure_length(graph.meter))


def _measure_length(meter: str | None) -> float:
    if not meter or "/" not in meter:
        return 4.0
    numerator_str, denominator_str = meter.split("/", 1)
    try:
        numerator = int(numerator_str)
        denominator = int(denominator_str)
    except ValueError:
        return 4.0
    return numerator * (4.0 / denominator)


def _measure_number_from_ref(ref_id: str) -> int | None:
    marker = ":m"
    if marker not in ref_id:
        return None
    suffix = ref_id.rsplit(marker, 1)[-1]
    digits = "".join(ch for ch in suffix if ch.isdigit())
    return int(digits) if digits else None


def _maybe_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _misc(item: Any) -> dict[str, Any]:
    editorial = getattr(item, "editorial", None)
    if editorial is None:
        return {}
    misc = getattr(editorial, "misc", None)
    if misc is None:
        editorial.misc = {}
        misc = editorial.misc
    return misc


def key_pitch_class(tonic: str) -> int:
    return note_name_to_midi(f"{tonic}4") % 12

