from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from bachbot.analysis import analyze_graph
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import TypedNote


@dataclass
class VoiceToken:
    notation: str
    duration_quarters: float
    measure_number: int
    onset: float
    is_rest: bool
    annotation_start: bool = False


def _measure_length(meter: str | None) -> float:
    if not meter or "/" not in meter:
        return 4.0
    beats_text, beat_type_text = meter.split("/", 1)
    beats = int(beats_text)
    beat_type = int(beat_type_text)
    return beats * (4.0 / beat_type)


def _duration_to_lily(duration_quarters: float) -> str:
    duration_quarters = round(duration_quarters, 4)
    mapping = {
        4.0: "1",
        3.0: "2.",
        2.0: "2",
        1.5: "4.",
        1.0: "4",
        0.75: "8.",
        0.5: "8",
        0.25: "16",
    }
    if duration_quarters not in mapping:
        raise ValueError(f"Unsupported duration for LilyPond export: {duration_quarters}")
    return mapping[duration_quarters]


def _pitch_parts(pitch: str) -> tuple[str, str, str | None]:
    match = re.fullmatch(r"([A-Ga-g])([b#]{0,2})(-?\d+)?", pitch)
    if not match:
        raise ValueError(f"Unsupported pitch spelling for LilyPond export: {pitch}")
    step, accidental, octave_text = match.groups()
    return step, accidental, octave_text


def _octave_from_text(octave_text: str | None) -> int:
    if octave_text is None:
        raise ValueError("Pitch spelling must include an octave when MIDI is unavailable")
    digits = octave_text.lstrip("-")
    sign = -1 if octave_text.startswith("-") else 1
    # DCML normalization can encode octaves like G33/F#44/D55. Collapse those to 3/4/5.
    if len(digits) > 1 and len(set(digits)) == 1:
        return sign * int(digits[-1])
    return int(octave_text)


def _pitch_to_lily(note: TypedNote) -> str:
    if note.pitch is None:
        raise ValueError("Pitch spelling required for LilyPond export")
    step, accidental, octave_text = _pitch_parts(note.pitch)
    octave = (note.midi // 12) - 1 if note.midi is not None else _octave_from_text(octave_text)
    accidental_suffix = {"": "", "#": "is", "##": "isis", "b": "es", "bb": "eses"}[accidental]
    octave_suffix = "'" * max(0, octave - 3) + "," * max(0, 3 - octave)
    return f"{step.lower()}{accidental_suffix}{octave_suffix}"


def _key_to_lily(tonic: str) -> str:
    try:
        step, accidental, _ = _pitch_parts(tonic)
    except ValueError:
        return tonic.lower()
    accidental_suffix = {"": "", "#": "is", "##": "isis", "b": "es", "bb": "eses"}[accidental]
    return f"{step.lower()}{accidental_suffix}"


def _ascii_roman(label: str) -> str:
    return label.replace("\u00b0", "o").replace("\u00f8", "o/")


def _split_note(note: TypedNote, measure_length: float) -> list[VoiceToken]:
    if note.is_rest or note.pitch is None:
        return []
    tokens: list[VoiceToken] = []
    remaining = note.duration_quarters
    segment_onset = note.offset_quarters
    first_segment = True
    while remaining > 1e-9:
        current_measure = int(segment_onset // measure_length) + 1
        boundary = current_measure * measure_length
        segment_duration = min(remaining, boundary - segment_onset if boundary > segment_onset else remaining)
        duration_token = _duration_to_lily(segment_duration)
        notation = f"{_pitch_to_lily(note)}{duration_token}"
        if remaining - segment_duration > 1e-9:
            notation += "~"
        if note.fermata and remaining - segment_duration <= 1e-9:
            notation += "\\fermata"
        tokens.append(
            VoiceToken(
                notation=notation,
                duration_quarters=segment_duration,
                measure_number=current_measure,
                onset=segment_onset,
                is_rest=False,
                annotation_start=first_segment,
            )
        )
        segment_onset += segment_duration
        remaining -= segment_duration
        first_segment = False
    return tokens


def _rest_token(onset: float, duration_quarters: float, measure_length: float) -> list[VoiceToken]:
    tokens: list[VoiceToken] = []
    remaining = duration_quarters
    segment_onset = onset
    while remaining > 1e-9:
        current_measure = int(segment_onset // measure_length) + 1
        boundary = current_measure * measure_length
        segment_duration = min(remaining, boundary - segment_onset if boundary > segment_onset else remaining)
        tokens.append(
            VoiceToken(
                notation=f"r{_duration_to_lily(segment_duration)}",
                duration_quarters=segment_duration,
                measure_number=current_measure,
                onset=segment_onset,
                is_rest=True,
            )
        )
        segment_onset += segment_duration
        remaining -= segment_duration
    return tokens


def _voice_tokens(graph: EventGraph, voice_id: str) -> list[VoiceToken]:
    notes = [note for note in graph.notes_by_voice().get(voice_id, []) if not note.is_rest]
    measure_length = _measure_length(graph.metadata.meter)
    cursor = 0.0
    tokens: list[VoiceToken] = []
    for note in notes:
        if note.offset_quarters > cursor:
            tokens.extend(_rest_token(cursor, note.offset_quarters - cursor, measure_length))
        tokens.extend(_split_note(note, measure_length))
        cursor = max(cursor, note.offset_quarters + note.duration_quarters)
    total_duration = graph.total_duration()
    if cursor < total_duration:
        tokens.extend(_rest_token(cursor, total_duration - cursor, measure_length))
    return tokens


def _apply_phrase_marks(tokens: list[VoiceToken], phrase_measures: set[int]) -> list[VoiceToken]:
    if not tokens:
        return tokens
    by_measure: dict[int, list[VoiceToken]] = defaultdict(list)
    for token in tokens:
        by_measure[token.measure_number].append(token)
    for measure in phrase_measures:
        measure_tokens = by_measure.get(measure)
        if measure_tokens:
            measure_tokens[-1].notation += "\\breathe"
    return tokens


def _render_voice(tokens: list[VoiceToken], final_measure: int) -> str:
    by_measure: dict[int, list[str]] = defaultdict(list)
    for token in tokens:
        by_measure[token.measure_number].append(token.notation)
    rendered_measures: list[str] = []
    for measure in range(1, final_measure + 1):
        measure_tokens = by_measure.get(measure, ["r1"])
        rendered_measures.append(" ".join(measure_tokens))
    return " |\n  ".join(rendered_measures)


def _markup_for_harmony(graph: EventGraph) -> tuple[dict[float, str], dict[float, str], set[int]]:
    report = analyze_graph(graph)
    roman_by_onset: dict[float, str] = {}
    figure_by_onset: dict[float, str] = {}
    for event in report.harmony:
        if event.roman_numeral_candidate_set:
            roman_by_onset[round(event.onset, 4)] = _ascii_roman(event.roman_numeral_candidate_set[0])
        figure_by_onset[round(event.onset, 4)] = event.figured_bass_like_summary or ""
    phrase_measures = {int(item["measure"]) for item in report.phrase_endings if "measure" in item}
    return roman_by_onset, figure_by_onset, phrase_measures


def _annotate_bass_tokens(tokens: list[VoiceToken], graph: EventGraph) -> tuple[list[VoiceToken], list[str]]:
    roman_by_onset, figure_by_onset, _ = _markup_for_harmony(graph)
    figure_tokens: list[str] = []
    annotated_tokens: list[VoiceToken] = []
    for token in tokens:
        key = round(token.onset, 4)
        if token.is_rest or not token.annotation_start:
            figure_tokens.append(f"s{_duration_to_lily(token.duration_quarters)}")
            annotated_tokens.append(token)
            continue
        roman = roman_by_onset.get(key)
        if roman:
            token.notation += f'_\\markup {{ "{roman}" }}'
        figures = figure_by_onset.get(key, "")
        if figures:
            figure_body = " ".join(part for part in figures.split("/") if part)
            figure_tokens.append(f"<{figure_body}>{_duration_to_lily(token.duration_quarters)}")
        else:
            figure_tokens.append(f"s{_duration_to_lily(token.duration_quarters)}")
        annotated_tokens.append(token)
    return annotated_tokens, figure_tokens


def event_graph_to_lilypond(graph: EventGraph) -> str:
    voice_map = graph.notes_by_voice()
    available = graph.ordered_voice_ids()
    required = ["S", "A", "T", "B"]
    if not all(voice_id in voice_map for voice_id in required):
        if len(available) < 4:
            raise ValueError("LilyPond export expects SATB voices")
        required = available[:4]
    roman_by_onset, _, phrase_measures = _markup_for_harmony(graph)
    del roman_by_onset
    soprano_tokens = _apply_phrase_marks(_voice_tokens(graph, required[0]), phrase_measures)
    alto_tokens = _voice_tokens(graph, required[1])
    tenor_tokens = _voice_tokens(graph, required[2])
    bass_tokens = _voice_tokens(graph, required[3])
    bass_tokens, figured_bass_tokens = _annotate_bass_tokens(bass_tokens, graph)

    key_estimate = graph.metadata.key_estimate
    if key_estimate is None:
        raise ValueError("Key estimate required for LilyPond export")
    title = graph.metadata.title or graph.work_id
    composer = graph.metadata.composer or "Johann Sebastian Bach"
    meter = graph.metadata.meter or "4/4"
    final_measure = max((note.measure_number for note in graph.notes), default=graph.section.measure_end)

    return (
        '\\version "2.24.0"\n'
        f'\\header {{\n  title = "{title}"\n  composer = "{composer}"\n}}\n\n'
        f'global = {{ \\key {_key_to_lily(key_estimate.tonic)} \\{key_estimate.mode} \\time {meter} }}\n\n'
        f'sopranoMusic = {{\n  \\global\n  {_render_voice(soprano_tokens, final_measure)}\n}}\n\n'
        f'altoMusic = {{\n  \\global\n  {_render_voice(alto_tokens, final_measure)}\n}}\n\n'
        f'tenorMusic = {{\n  \\global\n  {_render_voice(tenor_tokens, final_measure)}\n}}\n\n'
        f'bassMusic = {{\n  \\global\n  {_render_voice(bass_tokens, final_measure)}\n}}\n\n'
        'figuredBassMusic = \\figuremode {\n  '
        + " ".join(figured_bass_tokens)
        + "\n}\n\n"
        "\\score {\n"
        "  <<\n"
        '    \\new Staff = "upper" <<\n'
        "      \\clef treble\n"
        '      \\new Voice = "soprano" { \\voiceOne \\sopranoMusic }\n'
        '      \\new Voice = "alto" { \\voiceTwo \\altoMusic }\n'
        "    >>\n"
        '    \\new Staff = "lower" <<\n'
        "      \\clef bass\n"
        '      \\new Voice = "tenor" { \\voiceOne \\tenorMusic }\n'
        '      \\new Voice = "bass" { \\voiceTwo \\bassMusic }\n'
        "    >>\n"
        "    \\new FiguredBass \\figuredBassMusic\n"
        "  >>\n"
        "  \\layout { }\n"
        "}\n"
    )


def write_lilypond(graph: EventGraph, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(event_graph_to_lilypond(graph), encoding="utf-8")
    return path


def compile_lilypond(source_path: str | Path) -> Path:
    source = Path(source_path)
    output_prefix = source.with_suffix("")
    subprocess.run(
        ["lilypond", "-o", str(output_prefix), str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    pdf_path = output_prefix.with_suffix(".pdf")
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    return pdf_path
