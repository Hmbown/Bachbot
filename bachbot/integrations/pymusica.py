from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
import importlib
import importlib.util
import os
import re
import sys
import tomllib
from fractions import Fraction
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice


class PyMusicaUnavailableError(RuntimeError):
    """Raised when the optional PyMusica integration cannot be loaded."""


class ScoreIRUnsupportedError(RuntimeError):
    """Raised when a ScoreIR cannot be mapped into EventGraph deterministically."""


@dataclass(frozen=True)
class PyMusicaBackendStatus:
    available: bool
    discovery: str
    import_target: str | None = None
    requires_python: str | None = None
    current_python: str = f"{sys.version_info.major}.{sys.version_info.minor}"
    runtime_supported: bool = True
    message: str = ""


PYMUSICA_INTEGRATION_PYTHON_FLOOR = (3, 12)


def configured_pymusica_src() -> Path | None:
    """Return the explicitly configured PyMusica src path, if any."""

    env_value = os.getenv("BACHBOT_PYMUSICA_SRC", "").strip()
    if not env_value:
        return None
    return Path(env_value).expanduser()


def resolved_pymusica_src() -> Path | None:
    """Return a local PyMusica src path if one is discoverable."""

    configured = configured_pymusica_src()
    if configured is not None:
        return _validated_pymusica_src(
            configured,
            source="BACHBOT_PYMUSICA_SRC",
            required=True,
        )

    candidates: list[Path] = []
    repo_root = Path(__file__).resolve().parents[2]
    sibling_root = repo_root.parent
    candidates.extend(
        [
            sibling_root / "PyMusica" / "src",
            sibling_root / "pymusica" / "src",
            sibling_root / "pymusica_lang" / "src",
        ]
    )

    for candidate in candidates:
        resolved = _validated_pymusica_src(candidate, source="sibling checkout", required=False)
        if resolved is not None:
            return resolved
    return None


def pymusica_backend_status() -> PyMusicaBackendStatus:
    configured = configured_pymusica_src()
    resolved = resolved_pymusica_src() if configured is None else _validated_pymusica_src(configured, source="BACHBOT_PYMUSICA_SRC", required=False)
    current_python = f"{sys.version_info.major}.{sys.version_info.minor}"
    spec = importlib.util.find_spec("pymusica_lang")
    spec_origin = None if spec is None or spec.origin is None else Path(spec.origin).resolve()

    if spec_origin is not None:
        if configured is not None and _path_within(spec_origin, configured):
            discovery = "configured-src"
        elif resolved is not None and _path_within(spec_origin, resolved):
            discovery = "sibling-src"
        else:
            discovery = "installed"
        requires_python = _requires_python_for_path(spec_origin)
        runtime_supported = _runtime_supported(requires_python)
        import_target = str(spec_origin)
        return PyMusicaBackendStatus(
            available=True,
            discovery=discovery,
            import_target=import_target,
            requires_python=requires_python,
            current_python=current_python,
            runtime_supported=runtime_supported,
            message=_status_message(
                available=True,
                discovery=discovery,
                import_target=import_target,
                requires_python=requires_python,
                runtime_supported=runtime_supported,
                configured=configured,
            ),
        )

    if configured is not None:
        available = resolved is not None
        requires_python = _requires_python_for_path(configured) if configured.exists() else None
        runtime_supported = _runtime_supported(requires_python)
        import_target = str(configured)
        return PyMusicaBackendStatus(
            available=available,
            discovery="configured-src",
            import_target=import_target,
            requires_python=requires_python,
            current_python=current_python,
            runtime_supported=runtime_supported,
            message=_status_message(
                available=available,
                discovery="configured-src",
                import_target=import_target,
                requires_python=requires_python,
                runtime_supported=runtime_supported,
                configured=configured,
            ),
        )

    if resolved is not None:
        requires_python = _requires_python_for_path(resolved)
        runtime_supported = _runtime_supported(requires_python)
        import_target = str(resolved)
        return PyMusicaBackendStatus(
            available=True,
            discovery="sibling-src",
            import_target=import_target,
            requires_python=requires_python,
            current_python=current_python,
            runtime_supported=runtime_supported,
            message=_status_message(
                available=True,
                discovery="sibling-src",
                import_target=import_target,
                requires_python=requires_python,
                runtime_supported=runtime_supported,
                configured=configured,
            ),
        )

    return PyMusicaBackendStatus(
        available=False,
        discovery="unavailable",
        import_target=None,
        requires_python=None,
        current_python=current_python,
        runtime_supported=True,
        message=_status_message(
            available=False,
            discovery="unavailable",
            import_target=None,
            requires_python=None,
            runtime_supported=True,
            configured=configured,
        ),
    )


def pymusica_available() -> bool:
    try:
        _ensure_pymusica_importable()
    except PyMusicaUnavailableError:
        return False
    return True


def event_graph_to_score_ir(graph: EventGraph, *, tempo_bpm: int = 100) -> Any:
    """Map a Bachbot EventGraph into a PyMusica ScoreIR.

    The analysis core stays on EventGraph; this adapter only targets the
    general score/export substrate in PyMusica.
    """

    _ensure_pymusica_importable()

    from pymusica_lang.ir.events import Articulation, EventSequence, MusicEvent
    from pymusica_lang.ir.pitch import Pitch
    from pymusica_lang.ir.rhythm import Duration
    from pymusica_lang.ir.score import Meter, Part, ScoreIR, TempoMark, VoiceTrack

    meter = _coerce_meter(Meter, graph.meter)
    voices_by_id = {voice.voice_id: voice for voice in graph.voices}
    measure_refs = {measure.measure_number_logical: measure for measure in graph.measures}
    part_order: list[str] = []
    part_voices: dict[str, list[VoiceTrack]] = defaultdict(list)

    for voice_id in graph.ordered_voice_ids():
        voice = voices_by_id.get(voice_id)
        events = []
        grouped: dict[tuple[float, float], list[Any]] = {}
        for note in graph.notes_by_voice().get(voice_id, []):
            if note.is_rest or note.midi is None:
                continue
            key = (round(note.offset_quarters, 6), round(note.duration_quarters, 6))
            grouped.setdefault(key, []).append(note)

        for onset_value, duration_value in sorted(grouped):
            batch = sorted(grouped[(onset_value, duration_value)], key=lambda note: note.midi or -1)
            event_metadata = _event_metadata(batch=batch, voice_id=voice_id, measure_refs=measure_refs)
            events.append(
                MusicEvent(
                    onset=_quarter_fraction(onset_value),
                    duration=Duration(_quarter_fraction(duration_value)),
                    pitches=tuple(_pitch_from_note(note, Pitch) for note in batch),
                    articulation=_coerce_articulation(batch, Articulation),
                    metadata=event_metadata,
                )
            )

        normalized_name = (
            (voice.normalized_voice_name if voice else None)
            or (voice.part_name if voice else None)
            or voice_id
        )
        instrument = (
            (voice.instrument_or_role if voice and voice.instrument_or_role else None)
            or (voice.part_name if voice and voice.part_name else None)
            or normalized_name
        ).lower()
        part_name = (voice.part_name if voice and voice.part_name else normalized_name).strip()
        if part_name not in part_order:
            part_order.append(part_name)
        part_voices[part_name].append(
            VoiceTrack(
                name=voice_id,
                instrument=instrument,
                events=EventSequence(tuple(events), name=voice_id),
                annotations=_voice_annotations(voice_id=voice_id, normalized_name=normalized_name, voice=voice),
                metadata=_voice_metadata(voice_id=voice_id, normalized_name=normalized_name, voice=voice),
            )
        )

    metadata = {
        "bachbot_work_id": graph.work_id,
        "bachbot_encoding_id": graph.metadata.encoding_id,
        "bachbot_section_id": graph.section.section_id,
        "bachbot_section_label": graph.section.label,
        "bachbot_section_type": graph.section.section_type,
        "bachbot_section_measure_start": graph.section.measure_start,
        "bachbot_section_measure_end": graph.section.measure_end,
        "bachbot_source_format": graph.metadata.source_format,
        "bachbot_provenance": tuple(graph.metadata.provenance),
        "bachbot_voice_order": tuple(graph.ordered_voice_ids()),
        "bachbot_measure_map": tuple(
            {
                "measure_number_notated": measure.measure_number_notated,
                "measure_number_logical": measure.measure_number_logical,
                "onset": measure.onset,
                "duration": measure.duration,
                "voice_ids": tuple(measure.voice_ids),
            }
            for measure in graph.measures
        ),
    }
    if graph.source_path:
        metadata["bachbot_source_path"] = graph.source_path
    if graph.metadata.key_estimate is not None:
        metadata["bachbot_key_estimate_tonic"] = graph.metadata.key_estimate.tonic
        metadata["bachbot_key_estimate_mode"] = graph.metadata.key_estimate.mode
        metadata["bachbot_key_estimate_confidence"] = graph.metadata.key_estimate.confidence

    parts = tuple(
        Part(
            name=part_name,
            voices=tuple(part_voices[part_name]),
            annotations=(part_name,),
        )
        for part_name in part_order
    )

    return ScoreIR(
        title=graph.title,
        tempo=TempoMark(tempo_bpm),
        meter=meter,
        parts=parts,
        composer=graph.metadata.composer,
        metadata=metadata,
    )


def score_ir_to_event_graph(
    score: Any,
    *,
    work_id: str | None = None,
    encoding_id: str | None = None,
    source_path: str | None = None,
) -> EventGraph:
    """Map a deterministic PyMusica ScoreIR subset into a Bachbot EventGraph."""

    _ensure_pymusica_importable()

    from pymusica_lang.notation import measure_lengths, measure_starts, read_event_notation, read_score_notation, read_voice_notation

    if score.duration <= 0:
        raise ScoreIRUnsupportedError("ScoreIR -> EventGraph requires a positive-duration score")
    if not score.export_voices:
        raise ScoreIRUnsupportedError("ScoreIR -> EventGraph requires at least one voice")

    score_notation = read_score_notation(score)
    key_signature_context = _score_key_signature_context(score_notation)
    tempo_marking = _score_tempo_marking(score, score_notation)

    lengths = measure_lengths(score.duration, score.meter.quarter_length, score_notation)
    if not lengths:
        raise ScoreIRUnsupportedError("ScoreIR -> EventGraph could not derive measure boundaries")
    starts = measure_starts(lengths)
    numbers = _measure_numbers(score=score, starts=starts, lengths=lengths)

    metadata = _encoding_metadata_from_score(
        score=score,
        work_id=work_id,
        encoding_id=encoding_id,
        source_path=source_path,
    )
    section = _section_from_score(
        score=score,
        metadata=metadata,
        measure_numbers=numbers,
        tempo_marking=tempo_marking,
        key_signature_context=key_signature_context,
    )

    voices: list[Voice] = []
    notes: list[TypedNote] = []
    seen_voice_ids: set[str] = set()
    for part in score.parts:
        for voice in part.voices:
            voice_notation = read_voice_notation(voice)
            if voice_notation.has_content:
                raise ScoreIRUnsupportedError(
                    f"Voice {voice.name!r} uses transposition notation, which EventGraph cannot represent canonically"
                )
            if voice.dynamic is not None:
                raise ScoreIRUnsupportedError(
                    f"Voice {voice.name!r} declares a dynamic marking, which EventGraph cannot represent canonically"
                )

            voice_id, normalized_name, part_name = _voice_identity(part=part.name, voice=voice)
            if voice_id in seen_voice_ids:
                raise ScoreIRUnsupportedError(f"ScoreIR -> EventGraph requires unique voice ids; repeated {voice_id!r}")
            seen_voice_ids.add(voice_id)

            staff_id = _metadata_str(voice.metadata, "bachbot_staff_id")
            instrument_or_role = _metadata_str(voice.metadata, "bachbot_instrument_or_role") or voice.instrument or part_name
            range_profile = _range_profile(voice.metadata.get("bachbot_range_profile"))
            clef_profile = _metadata_str(voice.metadata, "bachbot_clef_profile")
            voices.append(
                Voice(
                    voice_id=voice_id,
                    section_id=section.section_id,
                    staff_id=staff_id,
                    part_name=part_name,
                    normalized_voice_name=normalized_name,
                    instrument_or_role=instrument_or_role,
                    range_profile=range_profile,
                    clef_profile=clef_profile,
                )
            )

            previous_end = Fraction(0, 1)
            for event in voice.events.events:
                notation = read_event_notation(event)
                if notation.has_content:
                    raise ScoreIRUnsupportedError(
                        f"Voice {voice_id!r} contains notation-only event overlays, which EventGraph cannot represent canonically"
                    )
                if event.dynamic is not None:
                    raise ScoreIRUnsupportedError(
                        f"Voice {voice_id!r} contains dynamic-marked events, which EventGraph cannot represent canonically"
                    )
                if event.onset < previous_end:
                    raise ScoreIRUnsupportedError(
                        f"Voice {voice_id!r} contains overlapping events at {float(event.onset):.6f}q"
                    )
                previous_end = event.end
                if len(event.pitches) > 1:
                    raise ScoreIRUnsupportedError(
                        f"Voice {voice_id!r} contains chords; EventGraph workflows require monophonic voices"
                    )

                measure_index = _measure_index_for_onset(event.onset, starts)
                measure_start = starts[measure_index]
                measure_length = lengths[measure_index]
                if event.end > measure_start + measure_length:
                    raise ScoreIRUnsupportedError(
                        f"Voice {voice_id!r} contains an event crossing a barline at measure {numbers[measure_index]}"
                    )

                measure_number = numbers[measure_index]
                _validate_event_metadata(event=event, voice_id=voice_id, measure_number=measure_number)

                offset = _quarter_float(event.onset)
                duration = _quarter_float(event.duration.quarter_length)
                beat = _quarter_float(event.onset - measure_start) + 1.0
                note = _typed_note_from_event(
                    event=event,
                    voice_id=voice_id,
                    part_name=part_name,
                    staff_id=staff_id,
                    section_id=section.section_id,
                    measure_number=measure_number,
                    offset=offset,
                    duration=duration,
                    beat=beat,
                )
                notes.append(note)

    return EventGraph(metadata=metadata, section=section, voices=voices, notes=notes)


def write_musicxml_with_pymusica(graph: EventGraph, path: str | Path, *, tempo_bpm: int = 100) -> Path:
    _ensure_pymusica_importable()

    from pymusica_lang.export import write_musicxml

    return write_musicxml(event_graph_to_score_ir(graph, tempo_bpm=tempo_bpm), path)


def event_graph_to_midi_with_pymusica(graph: EventGraph, *, tempo_bpm: int = 100) -> bytes:
    _ensure_pymusica_importable()

    from pymusica_lang.export import score_to_midi_bytes

    return score_to_midi_bytes(event_graph_to_score_ir(graph, tempo_bpm=tempo_bpm))


def write_midi_with_pymusica(graph: EventGraph, path: str | Path, *, tempo_bpm: int = 100) -> Path:
    _ensure_pymusica_importable()

    from pymusica_lang.export import write_midi

    return write_midi(event_graph_to_score_ir(graph, tempo_bpm=tempo_bpm), path)


def _ensure_pymusica_importable() -> None:
    try:
        importlib.import_module("pymusica_lang")
        return
    except ModuleNotFoundError as exc:
        if exc.name != "pymusica_lang":
            raise

    src_path = resolved_pymusica_src()
    if src_path is not None:
        src_text = str(src_path)
        if src_text not in sys.path:
            sys.path.insert(0, src_text)
            importlib.invalidate_caches()
        try:
            importlib.import_module("pymusica_lang")
            return
        except ModuleNotFoundError as exc:
            if exc.name != "pymusica_lang":
                raise

    status = pymusica_backend_status()
    raise PyMusicaUnavailableError(
        "PyMusica backend requested but pymusica_lang is not importable. "
        f"{status.message}"
    )


def _quarter_fraction(value: float) -> Fraction:
    return Fraction(str(round(value, 6))).limit_denominator(960)


def _quarter_float(value: Fraction | int | float) -> float:
    return round(float(value), 6)


def _coerce_meter(meter_cls: Any, value: str | None) -> Any:
    if not value:
        return meter_cls()
    try:
        return meter_cls.from_string(value)
    except Exception:
        return meter_cls()


def _pitch_from_note(note: Any, pitch_cls: Any) -> Any:
    spelling = _extract_spelling(note.pitch)
    return pitch_cls(midi=note.midi, spelling=spelling)


def _extract_spelling(value: str | None) -> str | None:
    if not value:
        return None
    match = re.match(r"^([A-Ga-g][#b]{0,2})", value)
    if not match:
        return None
    token = match.group(1)
    return token[0].upper() + token[1:]


def _coerce_articulation(notes: list[Any], articulation_cls: Any) -> Any:
    for note in notes:
        for articulation in getattr(note, "articulations", []):
            lowered = articulation.lower()
            if lowered in articulation_cls._value2member_map_:
                return articulation_cls(lowered)
    return None


def _voice_annotations(*, voice_id: str, normalized_name: str, voice: Any) -> tuple[str, ...]:
    labels: list[str] = [normalized_name]
    if voice and voice.part_name and voice.part_name not in labels:
        labels.append(voice.part_name)
    if voice_id not in labels:
        labels.append(voice_id)
    return tuple(labels)


def _voice_metadata(*, voice_id: str, normalized_name: str, voice: Any) -> dict[str, object]:
    metadata: dict[str, object] = {
        "bachbot_voice_id": voice_id,
        "bachbot_label": normalized_name,
        "bachbot_normalized_voice_name": normalized_name,
    }
    if not voice:
        return metadata
    if voice.part_name:
        metadata["bachbot_part_name"] = voice.part_name
    if voice.staff_id:
        metadata["bachbot_staff_id"] = voice.staff_id
    if voice.instrument_or_role:
        metadata["bachbot_instrument_or_role"] = voice.instrument_or_role
    if voice.range_profile is not None:
        metadata["bachbot_range_profile"] = tuple(voice.range_profile)
    if voice.clef_profile:
        metadata["bachbot_clef_profile"] = voice.clef_profile
    return metadata


def _event_metadata(*, batch: list[Any], voice_id: str, measure_refs: dict[int, Any]) -> dict[str, object]:
    anchor = batch[0]
    source_refs = tuple(dict.fromkeys(note.source_ref for note in batch if note.source_ref))
    articulations = tuple(dict.fromkeys(articulation for note in batch for articulation in note.articulations))
    accidentals = tuple(dict.fromkeys(note.accidental for note in batch if note.accidental))
    lyrics = tuple(dict.fromkeys(note.lyric for note in batch if note.lyric))
    measure_numbers = tuple(sorted({note.measure_number for note in batch}))
    metadata: dict[str, object] = {
        "measure_number": str(anchor.measure_number),
        "voice_id": voice_id,
        "bachbot_measure_number": anchor.measure_number,
        "bachbot_measure_numbers": measure_numbers,
        "bachbot_voice_id": voice_id,
        "bachbot_beat": anchor.beat,
        "bachbot_offset_quarters": anchor.offset_quarters,
        "bachbot_duration_quarters": anchor.duration_quarters,
    }
    if source_refs:
        metadata["bachbot_source_refs"] = source_refs
        metadata["bachbot_source_ref"] = source_refs[0]
    if anchor.staff_id:
        metadata["bachbot_staff_id"] = anchor.staff_id
    if anchor.part_name:
        metadata["bachbot_part_name"] = anchor.part_name
    if accidentals:
        metadata["bachbot_accidental"] = accidentals[0]
        metadata["bachbot_accidentals"] = accidentals
    if lyrics:
        metadata["bachbot_lyric"] = lyrics[0]
        metadata["bachbot_lyrics"] = lyrics
    if any(note.fermata for note in batch):
        metadata["bachbot_fermata"] = True
    if any(note.tie_start for note in batch):
        metadata["bachbot_tie_start"] = True
    if any(note.tie_stop for note in batch):
        metadata["bachbot_tie_stop"] = True
    if articulations:
        metadata["bachbot_articulations"] = articulations
    pitch_names = tuple(note.pitch for note in batch if note.pitch)
    if pitch_names:
        metadata["bachbot_pitch_names"] = pitch_names
    measure_ref = measure_refs.get(anchor.measure_number)
    if measure_ref is not None:
        metadata["bachbot_measure_number_notated"] = measure_ref.measure_number_notated
        metadata["bachbot_measure_number_logical"] = measure_ref.measure_number_logical
        metadata["bachbot_measure_onset"] = measure_ref.onset
        metadata["bachbot_measure_duration"] = measure_ref.duration
    return metadata


def _score_key_signature_context(score_notation: Any) -> str | None:
    if score_notation.pickup is not None:
        raise ScoreIRUnsupportedError("ScoreIR -> EventGraph does not support pickup measures")
    if score_notation.rehearsal_marks:
        raise ScoreIRUnsupportedError("ScoreIR -> EventGraph does not support rehearsal marks")
    if score_notation.repeats:
        raise ScoreIRUnsupportedError("ScoreIR -> EventGraph does not support repeat barlines")
    if score_notation.voltas:
        raise ScoreIRUnsupportedError("ScoreIR -> EventGraph does not support volta brackets")
    if len(score_notation.key_changes) > 1 or any(change.onset != 0 for change in score_notation.key_changes):
        raise ScoreIRUnsupportedError("ScoreIR -> EventGraph only supports a single initial key signature change")

    if not score_notation.key_changes:
        return None
    change = score_notation.key_changes[0]
    return f"fifths={change.fifths} mode={change.mode}"


def _score_tempo_marking(score: Any, score_notation: Any) -> str:
    if len(score_notation.tempo_changes) > 1 or any(change.onset != 0 for change in score_notation.tempo_changes):
        raise ScoreIRUnsupportedError("ScoreIR -> EventGraph only supports a single initial tempo change")
    if score_notation.tempo_changes:
        change = score_notation.tempo_changes[0]
        if change.bpm != score.tempo.bpm:
            raise ScoreIRUnsupportedError("Initial tempo change must agree with ScoreIR.tempo")
        return change.text or str(score.tempo)
    return str(score.tempo)


def _encoding_metadata_from_score(
    *,
    score: Any,
    work_id: str | None,
    encoding_id: str | None,
    source_path: str | None,
) -> EncodingMetadata:
    metadata = dict(score.metadata)
    resolved_encoding_id = encoding_id or _metadata_str(metadata, "bachbot_encoding_id") or _identifier_from_title(score.title, prefix="PYMUSICA")
    resolved_work_id = work_id or _metadata_str(metadata, "bachbot_work_id") or resolved_encoding_id
    resolved_source_path = source_path or _metadata_str(metadata, "bachbot_source_path")
    resolved_source_format = _metadata_str(metadata, "bachbot_source_format") or "pymusica-scoreir"
    resolved_provenance = _provenance(metadata.get("bachbot_provenance"))
    key_estimate = _key_estimate_from_score_metadata(metadata)
    return EncodingMetadata(
        encoding_id=resolved_encoding_id,
        work_id=resolved_work_id,
        source_path=resolved_source_path,
        title=score.title,
        composer=score.composer,
        source_format=resolved_source_format,
        key_estimate=key_estimate,
        meter=str(score.meter),
        provenance=resolved_provenance,
    )


def _section_from_score(
    *,
    score: Any,
    metadata: EncodingMetadata,
    measure_numbers: tuple[int, ...],
    tempo_marking: str,
    key_signature_context: str | None,
) -> Section:
    raw = dict(score.metadata)
    section_id = _metadata_str(raw, "bachbot_section_id") or f"{metadata.work_id}:section:1"
    measure_start = measure_numbers[0]
    measure_end = measure_numbers[-1]
    declared_start = _metadata_int(raw, "bachbot_section_measure_start")
    declared_end = _metadata_int(raw, "bachbot_section_measure_end")
    if declared_start is not None and declared_start != measure_start:
        raise ScoreIRUnsupportedError(
            f"ScoreIR section start {declared_start} disagrees with derived measure start {measure_start}"
        )
    if declared_end is not None and declared_end != measure_end:
        raise ScoreIRUnsupportedError(
            f"ScoreIR section end {declared_end} disagrees with derived measure end {measure_end}"
        )
    return Section(
        section_id=section_id,
        work_id=metadata.work_id or metadata.encoding_id,
        label=_metadata_str(raw, "bachbot_section_label") or score.title or metadata.encoding_id,
        section_type=_metadata_str(raw, "bachbot_section_type") or "import",
        tempo_marking=tempo_marking,
        key_signature_context=key_signature_context,
        meter_context=str(score.meter),
        measure_start=measure_start,
        measure_end=measure_end,
    )


def _measure_numbers(*, score: Any, starts: tuple[Fraction, ...], lengths: tuple[Fraction, ...]) -> tuple[int, ...]:
    raw_measure_map = score.metadata.get("bachbot_measure_map")
    if raw_measure_map is None:
        base = _metadata_int(score.metadata, "bachbot_section_measure_start") or 1
        return tuple(base + idx for idx in range(len(starts)))

    if not isinstance(raw_measure_map, (list, tuple)):
        raise ScoreIRUnsupportedError("bachbot_measure_map must be a list or tuple")
    if len(raw_measure_map) != len(starts):
        raise ScoreIRUnsupportedError("bachbot_measure_map does not match the derived ScoreIR measure count")

    numbers: list[int] = []
    previous: int | None = None
    for idx, item in enumerate(raw_measure_map):
        if not isinstance(item, Mapping):
            raise ScoreIRUnsupportedError("bachbot_measure_map entries must be mappings")
        logical = int(item["measure_number_logical"])
        notated = int(item.get("measure_number_notated", logical))
        if logical != notated:
            raise ScoreIRUnsupportedError(
                "ScoreIR -> EventGraph does not support diverging logical/notated measure numbers"
            )
        if not _float_matches(item.get("onset"), starts[idx]) or not _float_matches(item.get("duration"), lengths[idx]):
            raise ScoreIRUnsupportedError("bachbot_measure_map does not match the derived ScoreIR measure layout")
        if previous is not None and logical != previous + 1:
            raise ScoreIRUnsupportedError("ScoreIR -> EventGraph requires consecutive measure numbering")
        numbers.append(logical)
        previous = logical
    return tuple(numbers)


def _voice_identity(*, part: str, voice: Any) -> tuple[str, str, str]:
    metadata = dict(voice.metadata)
    part_name = _metadata_str(metadata, "bachbot_part_name") or part
    if _metadata_str(metadata, "bachbot_part_name") and part_name != part:
        raise ScoreIRUnsupportedError(
            f"Voice {voice.name!r} disagrees with its containing part name: {part_name!r} != {part!r}"
        )
    voice_id = _metadata_str(metadata, "bachbot_voice_id") or voice.name
    normalized_name = (
        _metadata_str(metadata, "bachbot_normalized_voice_name")
        or (str(voice.annotations[0]) if voice.annotations else None)
        or voice.name
    )
    return voice_id, normalized_name, part_name


def _range_profile(value: object) -> tuple[int, int] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    raise ScoreIRUnsupportedError("bachbot_range_profile must be a two-item sequence")


def _measure_index_for_onset(onset: Fraction, starts: tuple[Fraction, ...]) -> int:
    index = bisect_right(starts, onset) - 1
    if index < 0:
        raise ScoreIRUnsupportedError(f"Could not place event onset {float(onset):.6f}q into a measure")
    return index


def _validate_event_metadata(*, event: Any, voice_id: str, measure_number: int) -> None:
    metadata = dict(event.metadata)
    tagged_voice = _metadata_str(metadata, "bachbot_voice_id")
    if tagged_voice is not None and tagged_voice != voice_id:
        raise ScoreIRUnsupportedError(
            f"Event metadata voice id {tagged_voice!r} disagrees with containing voice {voice_id!r}"
        )
    tagged_measure = _metadata_int(metadata, "bachbot_measure_number")
    if tagged_measure is not None and tagged_measure != measure_number:
        raise ScoreIRUnsupportedError(
            f"Event metadata measure number {tagged_measure} disagrees with derived measure {measure_number}"
        )
    display_measure = metadata.get("measure_number")
    if display_measure is not None:
        try:
            if int(display_measure) != measure_number:
                raise ScoreIRUnsupportedError(
                    f"Event metadata measure number {display_measure!r} disagrees with derived measure {measure_number}"
                )
        except ValueError as exc:
            raise ScoreIRUnsupportedError("Event metadata measure_number must be an integer when present") from exc
    tagged_measures = metadata.get("bachbot_measure_numbers")
    if tagged_measures is not None:
        values = tuple(int(item) for item in tagged_measures)
        if values != (measure_number,):
            raise ScoreIRUnsupportedError(
                "ScoreIR -> EventGraph does not support multi-measure event metadata"
            )
    tagged_offset = metadata.get("bachbot_offset_quarters")
    if tagged_offset is not None and not _float_matches(tagged_offset, event.onset):
        raise ScoreIRUnsupportedError("Event metadata onset disagrees with the ScoreIR onset")
    tagged_duration = metadata.get("bachbot_duration_quarters")
    if tagged_duration is not None and not _float_matches(tagged_duration, event.duration.quarter_length):
        raise ScoreIRUnsupportedError("Event metadata duration disagrees with the ScoreIR duration")


def _typed_note_from_event(
    *,
    event: Any,
    voice_id: str,
    part_name: str,
    staff_id: str | None,
    section_id: str,
    measure_number: int,
    offset: float,
    duration: float,
    beat: float,
) -> TypedNote:
    metadata = dict(event.metadata)
    is_rest = event.is_rest
    if is_rest:
        pitch = None
        midi = None
        accidental = None
    else:
        pitch = _pitch_name_from_event(event, metadata)
        midi = int(event.pitches[0].midi)
        accidental = _metadata_str(metadata, "bachbot_accidental") or _accidental_from_pitch_name(pitch)

    source_ref = _metadata_str(metadata, "bachbot_source_ref") or _default_source_ref(
        section_id=section_id,
        measure_number=measure_number,
        voice_id=voice_id,
        onset=event.onset,
    )
    articulations = _articulations_from_event(event, metadata)
    return TypedNote(
        pitch=pitch,
        midi=midi,
        duration_quarters=duration,
        offset_quarters=offset,
        measure_number=measure_number,
        beat=beat,
        voice_id=voice_id,
        staff_id=staff_id,
        part_name=part_name,
        tie_start=bool(metadata.get("bachbot_tie_start", False)),
        tie_stop=bool(metadata.get("bachbot_tie_stop", False)),
        is_rest=is_rest,
        accidental=accidental,
        lyric=_metadata_str(metadata, "bachbot_lyric"),
        fermata=bool(metadata.get("bachbot_fermata", False)),
        articulations=articulations,
        source_ref=source_ref,
    )


def _pitch_name_from_event(event: Any, metadata: Mapping[str, object]) -> str:
    pitch_names = metadata.get("bachbot_pitch_names")
    if isinstance(pitch_names, (list, tuple)):
        if len(pitch_names) != 1:
            raise ScoreIRUnsupportedError("ScoreIR -> EventGraph only supports monophonic pitch-name metadata")
        return str(pitch_names[0])
    return event.pitches[0].name()


def _articulations_from_event(event: Any, metadata: Mapping[str, object]) -> list[str]:
    tagged = metadata.get("bachbot_articulations")
    if tagged is not None:
        if not isinstance(tagged, (list, tuple)):
            raise ScoreIRUnsupportedError("bachbot_articulations must be a list or tuple")
        return [str(item) for item in tagged]
    if event.articulation is None:
        return []
    return [str(event.articulation.value)]


def _accidental_from_pitch_name(value: str) -> str | None:
    match = re.match(r"^[A-G]([#b]{1,2})", value)
    if match is None:
        return None
    return match.group(1)


def _default_source_ref(*, section_id: str, measure_number: int, voice_id: str, onset: Fraction) -> str:
    return f"{section_id}:m{measure_number}:{voice_id}:{onset.numerator}_{onset.denominator}"


def _key_estimate_from_score_metadata(metadata: Mapping[str, object]) -> KeyEstimate | None:
    tonic = _metadata_str(metadata, "bachbot_key_estimate_tonic")
    mode = _metadata_str(metadata, "bachbot_key_estimate_mode")
    if tonic is None or mode is None:
        return None
    confidence_raw = metadata.get("bachbot_key_estimate_confidence", 0.5)
    return KeyEstimate(tonic=tonic, mode=mode, confidence=float(confidence_raw))


def _provenance(value: object) -> list[str]:
    if value is None:
        return ["pymusica:scoreir"]
    if not isinstance(value, (list, tuple)):
        raise ScoreIRUnsupportedError("bachbot_provenance must be a list or tuple")
    return [str(item) for item in value]


def _identifier_from_title(title: str, *, prefix: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").upper()
    return slug or prefix


def _metadata_str(metadata: Mapping[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    return str(value)


def _metadata_int(metadata: Mapping[str, object], key: str) -> int | None:
    value = metadata.get(key)
    if value is None:
        return None
    return int(value)


def _float_matches(raw: object, expected: Fraction | int | float) -> bool:
    if raw is None:
        return False
    try:
        return abs(float(raw) - _quarter_float(expected)) <= 1e-6
    except (TypeError, ValueError):
        raise ScoreIRUnsupportedError("Expected numeric measure metadata") from None


def _path_within(candidate: Path, root: Path) -> bool:
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def _requires_python_for_path(path: Path) -> str | None:
    pyproject = _find_pyproject(path)
    if pyproject is None:
        return None
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, dict):
        return None
    value = project.get("requires-python")
    if value is None:
        return None
    return str(value)


def _find_pyproject(path: Path) -> Path | None:
    start = path if path.is_dir() else path.parent
    for candidate in (start, *start.parents):
        pyproject = candidate / "pyproject.toml"
        if pyproject.exists():
            return pyproject
    return None


def _runtime_supported(requires_python: str | None) -> bool:
    if requires_python is None:
        return True
    match = re.fullmatch(r">=\s*(\d+)\.(\d+)", requires_python.strip())
    if match is None:
        return True
    required = (int(match.group(1)), int(match.group(2)))
    current = (sys.version_info.major, sys.version_info.minor)
    return current >= required


def _status_message(
    *,
    available: bool,
    discovery: str,
    import_target: str | None,
    requires_python: str | None,
    runtime_supported: bool,
    configured: Path | None,
) -> str:
    if available:
        base = f"Resolved PyMusica via {discovery}"
        if import_target is not None:
            base += f" at {import_target}"
        if requires_python is not None and not runtime_supported:
            return (
                f"{base}. PyMusica declares {requires_python}, but the current interpreter is "
                f"{sys.version_info.major}.{sys.version_info.minor}; use Python 3.12+ for the supported shared-runtime contract."
            )
        return base + "."

    if discovery == "configured-src" and configured is not None:
        return (
            f"BACHBOT_PYMUSICA_SRC is set to {configured}, but that path does not exist. "
            "Fix the configured path or unset it to use sibling discovery."
        )
    return "No installed pymusica_lang module or discoverable checkout was found. Set BACHBOT_PYMUSICA_SRC or install PyMusica into the active environment."


def _validated_pymusica_src(candidate: Path, *, source: str, required: bool) -> Path | None:
    candidate = candidate.expanduser()
    package_root = candidate / "pymusica_lang"
    if candidate.exists() and package_root.exists():
        return candidate
    if required:
        raise PyMusicaUnavailableError(
            f"{source} must point to a PyMusica src directory containing pymusica_lang: {candidate}"
        )
    return None
