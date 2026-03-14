from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.features.key_profiles import estimate_key_from_notes
from bachbot.models.base import TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice

PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NOTE_NAME_TO_PC = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}

VOICE_ABBREVIATIONS = {
    "soprano": "S",
    "alto": "A",
    "tenor": "T",
    "bass": "B",
}


def _strip_namespace(root: ET.Element) -> None:
    for element in root.iter():
        if "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]


def midi_from_pitch(step: str, alter: int, octave: int) -> int:
    return (octave + 1) * 12 + PITCH_CLASS[step] + alter


def pitch_name_from_xml(step: str, alter: int, octave: int) -> str:
    accidental = {2: "##", 1: "#", 0: "", -1: "b", -2: "bb"}.get(alter, "")
    return f"{step}{accidental}{octave}"


def note_name_to_midi(note_name: str) -> int:
    match = re.fullmatch(r"([A-G][b#]?)(-?\d+)", note_name)
    if not match:
        raise ValueError(note_name)
    name, octave_str = match.groups()
    return (int(octave_str) + 1) * 12 + NOTE_NAME_TO_PC[name]


def midi_to_note_name(midi: int) -> str:
    octave = midi // 12 - 1
    pc = midi % 12
    spellings = {0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F", 6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}
    return f"{spellings[pc]}{octave}"


def _canonical_voice_id(part_name: str, voice_number: str, existing: set[str]) -> str:
    normalized = part_name.strip().lower()
    base = VOICE_ABBREVIATIONS.get(normalized, part_name.strip() or f"V{voice_number}")
    if base not in existing:
        return base
    candidate = f"{base}:{voice_number}"
    if candidate not in existing:
        return candidate
    suffix = 2
    while f"{candidate}:{suffix}" in existing:
        suffix += 1
    return f"{candidate}:{suffix}"


def _parse_tie_flags(note: ET.Element) -> tuple[bool, bool]:
    tie_types = {item.attrib.get("type", "").lower() for item in note.findall("tie")}
    tie_types.update(item.attrib.get("type", "").lower() for item in note.findall("notations/tied"))
    return "start" in tie_types, "stop" in tie_types


def parse_musicxml(path: str | Path, work_id: str | None = None, encoding_id: str | None = None) -> EventGraph:
    tree = ET.parse(path)
    root = tree.getroot()
    _strip_namespace(root)
    if root.tag != "score-partwise":
        raise ValueError("Only score-partwise MusicXML is supported")

    title = root.findtext("./work/work-title") or Path(path).stem
    composer = root.findtext("./identification/creator[@type='composer']")
    part_names = {part.attrib["id"]: (part.findtext("part-name") or part.attrib["id"]) for part in root.findall("./part-list/score-part")}
    section = Section(
        section_id="section_1",
        work_id=work_id or Path(path).stem,
        label="Full score",
        section_type="movement",
        measure_start=1,
        measure_end=1,
    )
    voices: dict[str, Voice] = {}
    voice_lookup: dict[tuple[str, str], str] = {}
    notes: list[TypedNote] = []
    divisions = 1
    meter = None
    global_key_fifths = 0

    for part in root.findall("./part"):
        part_id = part.attrib.get("id", "P1")
        part_name = part_names.get(part_id, part_id)
        cursor = 0.0
        last_chord_onset = 0.0
        for measure in part.findall("measure"):
            measure_number = int(measure.attrib.get("number", "1"))
            measure_offset = cursor
            local_time = 0.0
            current_measure_duration = 0.0
            attributes = measure.find("attributes")
            if attributes is not None:
                divisions_text = attributes.findtext("divisions")
                if divisions_text:
                    divisions = int(divisions_text)
                fifths = attributes.findtext("key/fifths")
                if fifths is not None:
                    global_key_fifths = int(fifths)
                beats = attributes.findtext("time/beats")
                beat_type = attributes.findtext("time/beat-type")
                if beats and beat_type:
                    meter = f"{beats}/{beat_type}"
            for child in list(measure):
                if child.tag == "note":
                    is_chord = child.find("chord") is not None
                    is_rest = child.find("rest") is not None
                    duration_quarters = int(child.findtext("duration", "0")) / divisions
                    onset = last_chord_onset if is_chord else measure_offset + local_time
                    if not is_chord:
                        last_chord_onset = onset
                    voice_number = child.findtext("voice", "1")
                    voice_key = (part_id, voice_number)
                    voice_id = voice_lookup.get(voice_key)
                    if voice_id is None:
                        voice_id = _canonical_voice_id(part_name, voice_number, set(voices))
                        voice_lookup[voice_key] = voice_id
                        voices[voice_id] = Voice(
                            voice_id=voice_id,
                            section_id=section.section_id,
                            part_name=part_name,
                            normalized_voice_name=voice_id,
                            instrument_or_role=part_name,
                        )
                    pitch = None
                    midi = None
                    accidental = None
                    tie_start, tie_stop = _parse_tie_flags(child)
                    if not is_rest:
                        pitch_node = child.find("pitch")
                        step = pitch_node.findtext("step", "C")
                        alter = int(pitch_node.findtext("alter", "0"))
                        octave = int(pitch_node.findtext("octave", "4"))
                        pitch = pitch_name_from_xml(step, alter, octave)
                        midi = midi_from_pitch(step, alter, octave)
                        accidental = {1: "#", -1: "b", 2: "##", -2: "bb"}.get(alter)
                    notes.append(
                        TypedNote(
                            pitch=pitch,
                            midi=midi,
                            duration_quarters=duration_quarters,
                            offset_quarters=onset,
                            measure_number=measure_number,
                            beat=(onset - measure_offset) + 1.0,
                            voice_id=voice_id,
                            part_name=part_name,
                            tie_start=tie_start,
                            tie_stop=tie_stop,
                            is_rest=is_rest,
                            accidental=accidental,
                            lyric=child.findtext("lyric/text"),
                            fermata=child.find("notations/fermata") is not None,
                            source_ref=f"{section.section_id}:m{measure_number}",
                        )
                    )
                    if not is_chord:
                        local_time += duration_quarters
                    current_measure_duration = max(current_measure_duration, local_time)
                elif child.tag == "backup":
                    local_time -= int(child.findtext("duration", "0")) / divisions
                elif child.tag == "forward":
                    local_time += int(child.findtext("duration", "0")) / divisions
            cursor = measure_offset + current_measure_duration
            section.measure_end = max(section.measure_end, measure_number)

    tonic = {
        -7: "Cb",
        -6: "Gb",
        -5: "Db",
        -4: "Ab",
        -3: "Eb",
        -2: "Bb",
        -1: "F",
        0: "C",
        1: "G",
        2: "D",
        3: "A",
        4: "E",
        5: "B",
        6: "F#",
        7: "C#",
    }.get(global_key_fifths, "C")
    metadata = EncodingMetadata(
        encoding_id=encoding_id or Path(path).stem,
        work_id=work_id or Path(path).stem,
        source_path=str(Path(path)),
        title=title,
        composer=composer,
        source_format="musicxml",
        meter=meter,
        provenance=[f"Imported from MusicXML at {Path(path)}"],
        key_estimate=estimate_key_from_notes(notes, preferred_tonic=tonic),
    )
    return EventGraph(metadata=metadata, section=section, voices=list(voices.values()), notes=notes)
