"""Parse DCML-format notes + measures TSVs into an EventGraph."""

from __future__ import annotations

import csv
from fractions import Fraction
from pathlib import Path

from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.features.key_profiles import estimate_key_from_notes
from bachbot.models.base import TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice

KEYSIG_FIFTHS_TO_TONIC = {
    -7: "Cb", -6: "Gb", -5: "Db", -4: "Ab", -3: "Eb", -2: "Bb", -1: "F",
    0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
}

STAFF_VOICE_TO_ROLE = {
    (1, 1): "S",
    (1, 2): "A",
    (2, 1): "T",
    (2, 2): "B",
}


def _frac(value: str) -> float:
    if not value:
        return 0.0
    return float(Fraction(value))


def _pitch_name(name: str, octave: str) -> str | None:
    if not name or not octave:
        return None
    return f"{name}{octave}"


def _parse_tie_flags(tied: str) -> tuple[bool, bool]:
    normalized = tied.strip()
    if not normalized:
        return False, False
    if normalized == "1":
        return True, False
    if normalized == "-1":
        return False, True
    if normalized == "0":
        return True, True
    lowered = normalized.lower()
    return ("start" in lowered or "continue" in lowered, "stop" in lowered or "continue" in lowered)


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        return list(reader)


def parse_dcml_tsv(
    notes_path: str | Path,
    measures_path: str | Path | None = None,
    work_id: str | None = None,
    encoding_id: str | None = None,
    title: str | None = None,
) -> EventGraph:
    notes_path = Path(notes_path)
    stem = notes_path.stem.replace(".notes", "")
    work_id = work_id or stem
    encoding_id = encoding_id or stem

    rows = _read_tsv(notes_path)
    if not rows:
        raise ValueError(f"Empty notes TSV: {notes_path}")

    keysig: int | None = None
    meter: str | None = None
    if measures_path is not None:
        measures_path = Path(measures_path)
        if measures_path.exists():
            mrows = _read_tsv(measures_path)
            if mrows:
                first = mrows[0]
                ks = first.get("keysig", "")
                if ks:
                    keysig = int(ks)
                ts = first.get("timesig", "")
                if ts:
                    meter = ts

    voices: dict[str, Voice] = {}
    notes: list[TypedNote] = []
    max_mn = 1

    for row in rows:
        mn = int(row.get("mn", "1"))
        max_mn = max(max_mn, mn)
        quarterbeats = _frac(row.get("quarterbeats", "0"))
        duration_qb = _frac(row.get("duration_qb", "0"))
        staff = int(row.get("staff", "1"))
        voice = int(row.get("voice", "1"))
        midi_val = row.get("midi", "")
        name = row.get("name", "")
        octave = row.get("octave", "")
        mn_onset_str = row.get("mn_onset", "0")
        tied = row.get("tied", "")
        tie_start, tie_stop = _parse_tie_flags(tied)

        voice_id = STAFF_VOICE_TO_ROLE.get((staff, voice), f"V{staff}:{voice}")
        if voice_id not in voices:
            voices[voice_id] = Voice(
                voice_id=voice_id,
                section_id="section_1",
                part_name=voice_id,
                normalized_voice_name=voice_id,
                instrument_or_role=voice_id,
            )

        is_rest = not midi_val or not name
        midi = int(midi_val) if midi_val and not is_rest else None
        pitch = _pitch_name(name, octave) if not is_rest else None
        beat = _frac(mn_onset_str) + 1.0

        notes.append(TypedNote(
            pitch=pitch,
            midi=midi,
            duration_quarters=duration_qb,
            offset_quarters=quarterbeats,
            measure_number=mn,
            beat=beat,
            voice_id=voice_id,
            staff_id=str(staff),
            is_rest=is_rest,
            tie_start=tie_start,
            tie_stop=tie_stop,
            fermata=False,
            source_ref=f"section_1:m{mn}",
        ))

    section = Section(
        section_id="section_1",
        work_id=work_id,
        label="Full score",
        section_type="movement",
        measure_start=1,
        measure_end=max_mn,
    )

    # Ensure SATB ordering (soprano first, bass last) for voice-leading analysis
    satb_order = ["S", "A", "T", "B"]
    ordered_voices = [voices[vid] for vid in satb_order if vid in voices]
    ordered_voices += [v for v in voices.values() if v.voice_id not in satb_order]

    tonic = KEYSIG_FIFTHS_TO_TONIC.get(keysig) if keysig is not None else None
    metadata = EncodingMetadata(
        encoding_id=encoding_id,
        work_id=work_id,
        source_path=str(notes_path),
        title=title or stem,
        composer="J.S. Bach",
        source_format="dcml_tsv",
        meter=meter,
        provenance=[f"Imported from DCML TSV at {notes_path}"],
        key_estimate=estimate_key_from_notes(notes, preferred_tonic=tonic, keysig=keysig),
    )

    return EventGraph(metadata=metadata, section=section, voices=ordered_voices, notes=notes)
