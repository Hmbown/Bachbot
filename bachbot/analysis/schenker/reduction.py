from __future__ import annotations

from collections import defaultdict

from bachbot.analysis.form.phrase import infer_phrase_endings
from bachbot.analysis.harmony.cadence import detect_cadences, summarize_harmony
from bachbot.analysis.harmony.roman_candidates import NOTE_TO_PC, _best_chord_pcs
from bachbot.analysis.schenker.prolongation import detect_prolongation_spans
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.cadence import Cadence
from bachbot.models.harmonic_event import HarmonicEvent
from bachbot.models.schenker import Bassbrechung, ReductionLayer, SchenkerianAnalysis, StructuralNote, Urlinie

_MAJOR_SCALE_DEGREES = {0: 1, 2: 2, 4: 3, 5: 4, 7: 5, 9: 6, 11: 7}
_MINOR_SCALE_DEGREES = {0: 1, 2: 2, 3: 3, 5: 4, 7: 5, 8: 6, 10: 7, 11: 7}


def analyze_schenkerian(
    graph: EventGraph,
    harmony: list[HarmonicEvent] | None = None,
    cadences: list[Cadence] | None = None,
    phrase_endings: list[dict[str, object]] | None = None,
) -> SchenkerianAnalysis:
    key = graph.metadata.key_estimate
    if key is None:
        raise ValueError("Key estimate required")

    harmony_events = harmony if harmony is not None else summarize_harmony(graph)
    cadence_events = cadences if cadences is not None else detect_cadences(graph)
    phrase_data = phrase_endings if phrase_endings is not None else infer_phrase_endings(graph, cadences=cadence_events)
    encoding_id = graph.metadata.encoding_id
    global_key = f"{key.tonic} {key.mode}"

    foreground = _build_foreground_layer(graph, harmony_events, key, encoding_id)
    middleground = _build_middleground_layer(
        foreground,
        phrase_end_measures=[int(item["measure"]) for item in phrase_data if "measure" in item],
        cadence_measures={_measure_from_ref(item.ref_id) for item in cadence_events},
        encoding_id=encoding_id,
    )
    urlinie = _detect_urlinie(middleground.notes, phrase_data)
    bassbrechung = _detect_bassbrechung(middleground.notes)
    background = _build_background_layer(
        middleground,
        urlinie=urlinie,
        bassbrechung=bassbrechung,
        encoding_id=encoding_id,
    )
    _assign_background_parents(middleground, background)

    return SchenkerianAnalysis(
        encoding_id=encoding_id,
        global_key=global_key,
        foreground=foreground,
        middleground=middleground,
        background=background,
        urlinie=urlinie,
        bassbrechung=bassbrechung,
    )


def generate_reduction_candidates(graph: EventGraph) -> list[dict[str, object]]:
    analysis = analyze_schenkerian(graph)
    by_measure: dict[int, list[StructuralNote]] = defaultdict(list)
    for note in analysis.middleground.notes:
        by_measure[note.measure].append(note)
    return [
        {
            "measure": measure,
            "strategy": "retain middleground structural representatives",
            "voices": sorted({item.voice_id for item in notes}),
            "note_ids": [item.note_id for item in sorted(notes, key=lambda note: (note.voice_id, note.onset))],
        }
        for measure, notes in sorted(by_measure.items())
    ]


def _build_foreground_layer(
    graph: EventGraph,
    harmony_events: list[HarmonicEvent],
    key: KeyEstimate,
    encoding_id: str,
) -> ReductionLayer:
    notes: list[StructuralNote] = []
    sorted_notes = graph.pitch_events()
    event_index = 0
    for note in sorted_notes:
        while event_index + 1 < len(harmony_events) and harmony_events[event_index + 1].onset <= note.onset:
            event_index += 1
        event = harmony_events[event_index] if harmony_events else None
        local_key = _key_from_event(event, key)
        harmony_label = event.roman_numeral_candidate_set[0] if event and event.roman_numeral_candidate_set else None
        role = "structural" if _is_chord_tone(note, event, local_key) else "ornamental"
        source_note_id = _typed_note_id(note)
        notes.append(
            StructuralNote(
                note_id=f"{encoding_id}:fg:{source_note_id}",
                source_note_id=source_note_id,
                voice_id=note.voice_id,
                measure=note.measure_number,
                onset=note.onset,
                duration=note.duration,
                pitch=note.pitch,
                midi=note.midi,
                scale_degree=_scale_degree(note.midi, key),
                harmony_label=harmony_label,
                local_key=f"{local_key.tonic} {local_key.mode}",
                role=role,
            )
        )
    return ReductionLayer(level="foreground", notes=notes, spans=[])


def _build_middleground_layer(
    foreground: ReductionLayer,
    phrase_end_measures: list[int],
    cadence_measures: set[int],
    encoding_id: str,
) -> ReductionLayer:
    selected: list[StructuralNote] = []
    anchor_measures = set(phrase_end_measures) | set(cadence_measures)
    if foreground.notes:
        max_measure = max(note.measure for note in foreground.notes)
        anchor_measures |= {max_measure, max(1, max_measure - 1)}

    by_voice_measure: dict[str, dict[int, list[StructuralNote]]] = defaultdict(lambda: defaultdict(list))
    for note in foreground.notes:
        by_voice_measure[note.voice_id][note.measure].append(note)

    for voice_id, measures in by_voice_measure.items():
        voice_selected: list[StructuralNote] = []
        for measure, notes in sorted(measures.items()):
            structural = [note for note in notes if note.role == "structural"]
            pool = structural or notes
            if measure in anchor_measures:
                retained = _collapse_repeated_pitches(sorted(pool, key=lambda item: (item.onset, -(item.duration), item.midi or -1)))
            else:
                retained = [_choose_measure_representative(pool)]
            voice_selected.extend(retained)
        voice_selected = _dedupe_consecutive_pitches(sorted(voice_selected, key=lambda item: (item.onset, item.measure)))
        for note in voice_selected:
            selected.append(
                StructuralNote(
                    note_id=f"{encoding_id}:mg:{note.source_note_id}",
                    source_note_id=note.source_note_id,
                    voice_id=note.voice_id,
                    measure=note.measure,
                    onset=note.onset,
                    duration=note.duration,
                    pitch=note.pitch,
                    midi=note.midi,
                    scale_degree=note.scale_degree,
                    harmony_label=note.harmony_label,
                    local_key=note.local_key,
                    role="structural",
                )
            )

    selected.sort(key=lambda item: (item.onset, item.voice_id, item.measure))
    middleground = ReductionLayer(level="middleground", notes=selected, spans=detect_prolongation_spans(selected, encoding_id))
    _assign_foreground_parents(foreground, middleground)
    return middleground


def _build_background_layer(
    middleground: ReductionLayer,
    urlinie: Urlinie,
    bassbrechung: Bassbrechung,
    encoding_id: str,
) -> ReductionLayer:
    middleground_by_id = {note.note_id: note for note in middleground.notes}
    background_notes: list[StructuralNote] = []
    seen_sources: set[str] = set()

    for note_id in urlinie.note_ids:
        note = middleground_by_id.get(note_id)
        if note is None or note.source_note_id in seen_sources:
            continue
        seen_sources.add(note.source_note_id)
        background_notes.append(_background_note(note, encoding_id, "urlinie"))

    for note_id in bassbrechung.note_ids:
        note = middleground_by_id.get(note_id)
        if note is None or note.source_note_id in seen_sources:
            continue
        seen_sources.add(note.source_note_id)
        background_notes.append(_background_note(note, encoding_id, "bassbrechung"))

    background_notes.sort(key=lambda item: (item.onset, item.voice_id, item.measure))
    return ReductionLayer(level="background", notes=background_notes, spans=detect_prolongation_spans(background_notes, encoding_id))


def _background_note(note: StructuralNote, encoding_id: str, role: str) -> StructuralNote:
    return StructuralNote(
        note_id=f"{encoding_id}:bg:{note.source_note_id}",
        source_note_id=note.source_note_id,
        voice_id=note.voice_id,
        measure=note.measure,
        onset=note.onset,
        duration=note.duration,
        pitch=note.pitch,
        midi=note.midi,
        scale_degree=note.scale_degree,
        harmony_label=note.harmony_label,
        local_key=note.local_key,
        role=role,
    )


def _assign_foreground_parents(foreground: ReductionLayer, middleground: ReductionLayer) -> None:
    mg_lookup: dict[str, list[StructuralNote]] = defaultdict(list)
    for note in middleground.notes:
        mg_lookup[note.voice_id].append(note)
    for notes in mg_lookup.values():
        notes.sort(key=lambda item: (item.measure, item.onset))

    for note in foreground.notes:
        candidates = mg_lookup.get(note.voice_id, [])
        if not candidates:
            continue
        same_measure = [candidate for candidate in candidates if candidate.measure == note.measure]
        pool = same_measure or candidates
        parent = min(pool, key=lambda candidate: (abs(candidate.onset - note.onset), abs(candidate.measure - note.measure)))
        note.parent_note_id = parent.note_id


def _assign_background_parents(middleground: ReductionLayer, background: ReductionLayer) -> None:
    bg_lookup: dict[str, list[StructuralNote]] = defaultdict(list)
    for note in background.notes:
        bg_lookup[note.voice_id].append(note)
    for notes in bg_lookup.values():
        notes.sort(key=lambda item: (item.measure, item.onset))

    for note in middleground.notes:
        candidates = bg_lookup.get(note.voice_id, [])
        if not candidates:
            continue
        earlier = [candidate for candidate in candidates if candidate.onset <= note.onset]
        later = [candidate for candidate in candidates if candidate.onset >= note.onset]
        if earlier and later:
            parent = later[0] if abs(later[0].onset - note.onset) <= abs(note.onset - earlier[-1].onset) else earlier[-1]
        else:
            parent = later[0] if later else earlier[-1]
        note.parent_note_id = parent.note_id


def _detect_urlinie(notes: list[StructuralNote], phrase_endings: list[dict[str, object]]) -> Urlinie:
    soprano = sorted((note for note in notes if note.voice_id == "S" and note.scale_degree is not None), key=lambda item: (item.onset, item.measure))
    if len(soprano) < 2:
        return Urlinie()

    final_note = _find_final_tonic(soprano)
    phrase_measures = sorted(int(item["measure"]) for item in phrase_endings if "measure" in item)
    candidate_pools = [
        _tail_pool(soprano, phrase_measures, final_note.measure),
        soprano,
    ]
    templates = ([8, 7, 6, 5, 4, 3, 2, 1], [5, 4, 3, 2, 1], [3, 2, 1])

    for pool_index, pool in enumerate(candidate_pools):
        if not pool:
            continue
        for template in templates:
            matched = _match_urlinie_template(pool, template, final_note)
            if matched:
                return Urlinie(
                    detected=True,
                    degrees=[_extended_degree(note, final_note) for note in matched],
                    note_ids=[note.note_id for note in matched],
                    measure_start=matched[0].measure,
                    measure_end=matched[-1].measure,
                    confidence=round(0.92 - pool_index * 0.08 - (0.0 if len(template) >= 5 else 0.12), 2),
                )
    return Urlinie()


def _detect_bassbrechung(notes: list[StructuralNote]) -> Bassbrechung:
    bass = sorted((note for note in notes if note.voice_id == "B" and note.scale_degree is not None), key=lambda item: (item.onset, item.measure))
    if len(bass) < 3:
        return Bassbrechung()

    final_tonic = _find_final_tonic(bass)
    dominant = next((note for note in reversed(bass[: bass.index(final_tonic)]) if note.scale_degree == 5), None)
    if dominant is None:
        return Bassbrechung()
    opening = next((note for note in bass if note.onset < dominant.onset and note.scale_degree == 1), bass[0])
    if opening.onset >= dominant.onset or dominant.onset >= final_tonic.onset:
        return Bassbrechung()

    return Bassbrechung(
        detected=True,
        degrees=[1, 5, 1],
        note_ids=[opening.note_id, dominant.note_id, final_tonic.note_id],
        measure_start=opening.measure,
        measure_end=final_tonic.measure,
        confidence=0.82,
    )


def _match_urlinie_template(
    notes: list[StructuralNote],
    template: list[int],
    final_note: StructuralNote,
) -> list[StructuralNote] | None:
    if not notes or _extended_degree(final_note, final_note) != template[-1]:
        return None
    try:
        end_index = notes.index(final_note)
    except ValueError:
        return None

    matched = [final_note]
    current_index = end_index
    current_midi = final_note.midi or 0
    for degree in reversed(template[:-1]):
        found = None
        for index in range(current_index - 1, -1, -1):
            candidate = notes[index]
            candidate_degree = _extended_degree(candidate, final_note)
            if candidate_degree != degree:
                continue
            if candidate.midi is not None and candidate.midi < current_midi:
                continue
            found = candidate
            current_index = index
            current_midi = candidate.midi or current_midi
            break
        if found is None:
            return None
        matched.append(found)
    return list(reversed(matched))


def _tail_pool(notes: list[StructuralNote], phrase_measures: list[int], final_measure: int) -> list[StructuralNote]:
    if not phrase_measures:
        return [note for note in notes if note.measure >= max(1, final_measure - 4)]
    previous_phrase_end = 0
    for measure in phrase_measures:
        if measure < final_measure:
            previous_phrase_end = measure
    start_measure = max(1, previous_phrase_end)
    return [note for note in notes if note.measure >= start_measure]


def _find_final_tonic(notes: list[StructuralNote]) -> StructuralNote:
    for note in reversed(notes):
        if note.scale_degree == 1:
            return note
    return notes[-1]


def _extended_degree(note: StructuralNote, final_note: StructuralNote) -> int:
    if note.scale_degree != 1 or note.midi is None or final_note.midi is None:
        return note.scale_degree or 0
    return 8 if note.midi > final_note.midi + 2 else 1


def _choose_measure_representative(notes: list[StructuralNote]) -> StructuralNote:
    return max(notes, key=lambda item: (item.duration, item.onset == 0.0, -(item.midi or -1)))


def _collapse_repeated_pitches(notes: list[StructuralNote]) -> list[StructuralNote]:
    collapsed: list[StructuralNote] = []
    last_midi: int | None = None
    for note in notes:
        if note.midi == last_midi:
            continue
        collapsed.append(note)
        last_midi = note.midi
    return collapsed or notes[:1]


def _dedupe_consecutive_pitches(notes: list[StructuralNote]) -> list[StructuralNote]:
    deduped: list[StructuralNote] = []
    for note in notes:
        if deduped and deduped[-1].midi == note.midi:
            if note.duration > deduped[-1].duration:
                deduped[-1] = note
            continue
        deduped.append(note)
    return deduped


def _is_chord_tone(note: TypedNote, event: HarmonicEvent | None, local_key: KeyEstimate) -> bool:
    if note.midi is None or event is None or not event.roman_numeral_candidate_set:
        return True
    relative_pc = (note.midi % 12 - NOTE_TO_PC.get(local_key.tonic, 0)) % 12
    chord_pcs = _best_chord_pcs(event.roman_numeral_candidate_set, local_key)
    return relative_pc in chord_pcs if chord_pcs else True


def _key_from_event(event: HarmonicEvent | None, fallback: KeyEstimate) -> KeyEstimate:
    if event is None or not event.local_key:
        return fallback
    parts = event.local_key.split()
    tonic = parts[0] if parts else fallback.tonic
    mode = parts[1] if len(parts) > 1 else fallback.mode
    return KeyEstimate(tonic=tonic, mode=mode, confidence=fallback.confidence)


def _scale_degree(midi: int | None, key: KeyEstimate) -> int | None:
    if midi is None:
        return None
    relative_pc = (midi % 12 - NOTE_TO_PC.get(key.tonic, 0)) % 12
    mapping = _MAJOR_SCALE_DEGREES if key.mode == "major" else _MINOR_SCALE_DEGREES
    return mapping.get(relative_pc)


def _typed_note_id(note: TypedNote) -> str:
    source = note.source_ref or f"m{note.measure_number}"
    midi = note.midi if note.midi is not None else "x"
    return f"{source}:{note.voice_id}:{int(note.onset * 100)}:{midi}"


def _measure_from_ref(ref_id: str) -> int:
    parts = ref_id.rsplit("m", 1)
    if len(parts) == 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 1
