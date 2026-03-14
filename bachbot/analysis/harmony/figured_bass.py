from __future__ import annotations

from bachbot.analysis.harmony.roman_candidates import (
    MAJOR,
    MAJOR_7TH,
    MINOR,
    MINOR_7TH,
    NOTE_TO_PC,
    _DEGREE_ROOTS,
    _secondary_dom_templates,
)
from bachbot.analysis.harmony.verticalities import build_verticalities
from bachbot.encodings.event_graph import EventGraph, VerticalitySlice
from bachbot.models.base import KeyEstimate
from bachbot.models.figured_bass import FiguredBassEvent, FiguredBassLine
from bachbot.models.harmonic_event import HarmonicEvent

_INTERVAL_TO_GENERIC = {
    1: 2,
    2: 2,
    3: 3,
    4: 3,
    5: 4,
    6: 4,
    7: 5,
    8: 6,
    9: 6,
    10: 7,
    11: 7,
}
_LETTER_TO_INDEX = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}

_PRIMARY_ROOTS = {
    "V7": "V",
    "viiø7": "vii°",
    "ii7": "ii",
    "IV7": "IV",
    "vi7": "vi",
    "viio7": "vii°",
    "iiø7": "ii°",
    "iv7": "iv",
    "VI7": "VI",
}


def _parse_local_key(key_label: str | None, fallback: KeyEstimate) -> KeyEstimate:
    if not key_label:
        return fallback
    parts = key_label.split()
    tonic = parts[0] if parts else fallback.tonic
    mode = parts[1] if len(parts) > 1 else fallback.mode
    return KeyEstimate(tonic=tonic, mode=mode)


def _signature(slice_: VerticalitySlice) -> tuple[int, ...]:
    bass = slice_.bass_note
    if bass is None or bass.midi is None:
        return ()
    generic_intervals = set()
    for note in slice_.active_notes:
        if note.midi is None or note.is_rest or note.midi == bass.midi:
            continue
        generic = _generic_interval_number(bass.pitch, note.pitch, (note.midi - bass.midi) % 12)
        if generic is not None:
            generic_intervals.add(generic)
    return tuple(sorted(generic_intervals))


def _pitch_token(pitch: str | None) -> str | None:
    if not pitch:
        return None
    token: list[str] = []
    for character in pitch:
        if character.isdigit():
            break
        token.append(character)
    return "".join(token) or None


def _generic_interval_number(
    bass_pitch: str | None,
    upper_pitch: str | None,
    semitone_distance: int,
) -> int | None:
    bass_token = _pitch_token(bass_pitch)
    upper_token = _pitch_token(upper_pitch)
    if bass_token and upper_token:
        bass_letter = _LETTER_TO_INDEX.get(bass_token[0].upper())
        upper_letter = _LETTER_TO_INDEX.get(upper_token[0].upper())
        if bass_letter is not None and upper_letter is not None:
            return ((upper_letter - bass_letter) % 7) + 1
    return _INTERVAL_TO_GENERIC.get(semitone_distance)


def _signature_to_figures(signature: tuple[int, ...]) -> list[str] | None:
    if not signature:
        return None
    signature_set = set(signature)
    if {2, 4, 6}.issubset(signature_set):
        return ["4", "2"]
    if {3, 4, 6}.issubset(signature_set):
        return ["4", "3"]
    if {3, 5, 6}.issubset(signature_set):
        return ["6", "5"]
    if {3, 5, 7}.issubset(signature_set):
        return ["7"]
    if {4, 6}.issubset(signature_set):
        return ["6", "4"]
    if {3, 6}.issubset(signature_set):
        return ["6"]
    if {3, 5}.issubset(signature_set):
        return []
    return None


def _candidate_pitch_classes(label: str, key: KeyEstimate) -> tuple[int | None, set[int], bool]:
    families = MAJOR if key.mode == "major" else MINOR
    sevenths = MAJOR_7TH if key.mode == "major" else MINOR_7TH
    if label in families:
        root_degree = _DEGREE_ROOTS.get(label)
        return root_degree, set(families[label]), False
    if label in sevenths:
        root_degree = _DEGREE_ROOTS.get(_PRIMARY_ROOTS.get(label, label))
        return root_degree, set(sevenths[label]), True
    if "/" in label:
        quality, target = label.split("/", 1)
        target_root = _DEGREE_ROOTS.get(target)
        if target_root is None:
            return None, set(), False
        for prefix, chord_pcs in _secondary_dom_templates(target_root):
            if prefix == quality:
                dominant_root = (target_root + 7) % 12 if quality.startswith("V") else (target_root + 11) % 12
                return dominant_root, set(chord_pcs), "7" in quality
    return None, set(), "7" in label


def _candidate_figures(event: HarmonicEvent, slice_: VerticalitySlice, global_key: KeyEstimate) -> list[str]:
    bass = slice_.bass_note
    if bass is None or bass.midi is None or not event.roman_numeral_candidate_set:
        return []
    effective_key = _parse_local_key(event.local_key, global_key)
    tonic_pc = NOTE_TO_PC.get(effective_key.tonic, NOTE_TO_PC.get(global_key.tonic, 0))
    primary = event.roman_numeral_candidate_set[0]
    root_degree, _, has_seventh = _candidate_pitch_classes(primary, effective_key)
    if root_degree is None:
        return []
    root_pc = (tonic_pc + root_degree) % 12
    bass_interval = (bass.midi % 12 - root_pc) % 12
    if bass_interval == 0:
        return ["7"] if has_seventh else []
    if bass_interval in {3, 4}:
        return ["6", "5"] if has_seventh else ["6"]
    if bass_interval in {6, 7}:
        return ["4", "3"] if has_seventh else ["6", "4"]
    if bass_interval in {9, 10, 11}:
        return ["4", "2"] if has_seventh else []
    return []


def _event_figures(slice_: VerticalitySlice, event: HarmonicEvent, global_key: KeyEstimate) -> list[str]:
    signature_match = _signature_to_figures(_signature(slice_))
    if signature_match is not None:
        return signature_match
    return _candidate_figures(event, slice_, global_key)


def extract_figured_bass_from_events(
    slices: list[VerticalitySlice],
    events: list[HarmonicEvent],
    *,
    work_id: str,
    encoding_id: str,
    key: KeyEstimate,
) -> FiguredBassLine:
    figured_events: list[FiguredBassEvent] = []
    for slice_, event in zip(slices, events):
        figures = _event_figures(slice_, event, key)
        summary = "/".join(figures) if figures else ""
        event.figured_bass_like_summary = summary
        figured_events.append(
            FiguredBassEvent(
                onset=slice_.onset,
                measure_number=slice_.measure_number,
                bass_pitch=slice_.bass_note.pitch if slice_.bass_note else None,
                figures=figures,
                figure_summary=summary,
                harmonic_event_id=event.harmonic_event_id,
                roman_numeral=event.roman_numeral_candidate_set[0] if event.roman_numeral_candidate_set else None,
            )
        )
    return FiguredBassLine(work_id=work_id, encoding_id=encoding_id, events=figured_events)


def extract_figured_bass(graph: EventGraph) -> FiguredBassLine:
    from bachbot.analysis.harmony.cadence import summarize_harmony

    key = graph.metadata.key_estimate
    if key is None:
        raise ValueError("Key estimate required")
    slices = build_verticalities(graph)
    events = summarize_harmony(graph)
    return extract_figured_bass_from_events(
        slices,
        events,
        work_id=graph.work_id,
        encoding_id=graph.metadata.encoding_id,
        key=key,
    )
