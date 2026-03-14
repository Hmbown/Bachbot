from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from bachbot.encodings.event_graph import EventGraph
from bachbot.integrations.pymusica import (
    PyMusicaUnavailableError,
    write_musicxml_with_pymusica,
)


DIVISIONS_PER_QUARTER = 4


def _musicxml_type_and_dots(duration_quarters: float) -> tuple[str, int]:
    duration_quarters = round(duration_quarters, 4)
    if duration_quarters == 4.0:
        return "whole", 0
    if duration_quarters == 3.0:
        return "half", 1
    if duration_quarters == 2.0:
        return "half", 0
    if duration_quarters == 1.5:
        return "quarter", 1
    if duration_quarters == 1.0:
        return "quarter", 0
    if duration_quarters == 0.75:
        return "eighth", 1
    if duration_quarters == 0.5:
        return "eighth", 0
    if duration_quarters == 0.25:
        return "16th", 0
    return "quarter", 0


def write_musicxml(
    graph: EventGraph,
    path: str | Path,
    *,
    backend: str = "native",
    tempo_bpm: int = 100,
) -> Path:
    backend_name = backend.lower()
    if backend_name not in {"native", "pymusica", "auto"}:
        raise ValueError(f"Unsupported MusicXML backend: {backend}")
    if backend_name != "native":
        try:
            return write_musicxml_with_pymusica(graph, path, tempo_bpm=tempo_bpm)
        except PyMusicaUnavailableError:
            if backend_name == "pymusica":
                raise

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    grouped = defaultdict(list)
    for note in graph.notes:
        grouped[note.voice_id].append(note)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<score-partwise version="3.1">', "  <part-list>"]
    for index, voice in enumerate(graph.voices, start=1):
        lines.extend([f'    <score-part id="P{index}">', f"      <part-name>{voice.normalized_voice_name}</part-name>", "    </score-part>"])
    lines.append("  </part-list>")
    for index, voice in enumerate(graph.voices, start=1):
        lines.append(f'  <part id="P{index}">')
        by_measure = defaultdict(list)
        for note in grouped[voice.voice_id]:
            by_measure[note.measure_number].append(note)
        for measure_number in sorted(by_measure):
            lines.append(f'    <measure number="{measure_number}">')
            if measure_number == 1:
                lines.extend(
                    [
                        "      <attributes>",
                        f"        <divisions>{DIVISIONS_PER_QUARTER}</divisions>",
                        "        <time><beats>4</beats><beat-type>4</beat-type></time>",
                        "      </attributes>",
                    ]
                )
            for note in sorted(by_measure[measure_number], key=lambda item: (item.offset_quarters, item.voice_id, item.midi or -1)):
                step = note.pitch[0]
                alter = "          <alter>1</alter>" if "#" in note.pitch else "          <alter>-1</alter>" if "b" in note.pitch else None
                octave = note.pitch[-1]
                duration = int(round(note.duration_quarters * DIVISIONS_PER_QUARTER))
                note_type, dots = _musicxml_type_and_dots(note.duration_quarters)
                lines.extend(
                    [
                        "      <note>",
                        "        <pitch>",
                        f"          <step>{step}</step>",
                        *([alter] if alter else []),
                        f"          <octave>{octave}</octave>",
                        "        </pitch>",
                        f"        <duration>{duration}</duration>",
                        "        <voice>1</voice>",
                        f"        <type>{note_type}</type>",
                        *(["        <dot/>"] * dots),
                        "      </note>",
                    ]
                )
            lines.append("    </measure>")
        lines.append("  </part>")
    lines.append("</score-partwise>")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
