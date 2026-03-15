from __future__ import annotations

from bachbot.analysis.harmony.bass_patterns import extract_formula
from bachbot.analysis.harmony.figured_bass import extract_figured_bass_from_events
from bachbot.analysis.harmony.roman_candidates import (
    detect_secondary_dominants,
    estimate_local_key,
    harmonic_event_from_slice,
    tag_nonharmonic_tones,
)
from bachbot.analysis.harmony.verticalities import build_verticalities
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.cadence import Cadence
from bachbot.models.harmonic_event import HarmonicEvent


def summarize_harmony(graph: EventGraph) -> list[HarmonicEvent]:
    key = graph.metadata.key_estimate
    if key is None:
        raise ValueError("Key estimate required")
    slices = build_verticalities(graph)
    events = []
    for i, slice_ in enumerate(slices):
        local_key = estimate_local_key(slices, i, key)
        events.append(harmonic_event_from_slice(slice_, key, graph.metadata.encoding_id, local_key=local_key))
    detect_secondary_dominants(events, slices, key)
    tag_nonharmonic_tones(slices, events, key)
    extract_figured_bass_from_events(
        slices,
        events,
        work_id=graph.work_id,
        encoding_id=graph.metadata.encoding_id,
        key=key,
    )
    return events


def _has_tonic_resolution(candidates: set[str]) -> bool:
    return bool({"I", "i"} & candidates)


def _has_dominant_function(candidates: set[str]) -> bool:
    return bool({"V", "V7", "vii°", "viiø7", "viio7"} & candidates)


def _has_deceptive_target(candidates: set[str]) -> bool:
    return bool({"vi", "VI"} & candidates)


def _has_plagal_function(candidates: set[str]) -> bool:
    return bool({"IV", "iv", "IV7", "iv7"} & candidates)


def _score_cadence_pair(prev_slice, final_slice, penultimate, final, key):
    score = 0.0
    evidence: list[str] = []
    penultimate_candidates = set(penultimate.roman_numeral_candidate_set)
    final_candidates = set(final.roman_numeral_candidate_set)
    primary_final = final.roman_numeral_candidate_set[0] if final.roman_numeral_candidate_set else None
    if _has_tonic_resolution(final_candidates):
        score += 0.28
        evidence.append("final tonic support")
    if _has_deceptive_target(final_candidates):
        score += 0.2
        evidence.append("deceptive resolution")
    if _has_dominant_function(penultimate_candidates):
        score += 0.22
        evidence.append("dominant-like penultimate")
    bass_formula = extract_formula(prev_slice, final_slice, kind="bass", key=key)
    soprano_formula = extract_formula(prev_slice, final_slice, kind="soprano", key=key)
    if bass_formula in {"2-1", "5-1", "5-6", "7-1", "6-5", "4-1"}:
        score += 0.15
        evidence.append(f"bass formula {bass_formula}")
    if soprano_formula in {"2-1", "7-1", "7-6"}:
        score += 0.15
        evidence.append(f"soprano formula {soprano_formula}")
    if any(note.fermata for note in final_slice.active_notes):
        score += 0.25
        evidence.append("fermata")
    candidates = []
    # DC: primary candidate is deceptive target, or deceptive target in set without tonic
    is_deceptive = (
        primary_final in {"vi", "VI"}
        or (_has_deceptive_target(final_candidates) and not _has_tonic_resolution(final_candidates))
    )
    if is_deceptive and _has_dominant_function(penultimate_candidates):
        candidates.append("DC")
    elif _has_tonic_resolution(final_candidates) and _has_dominant_function(penultimate_candidates):
        candidates.append("PAC" if bass_formula == "5-1" else "IAC")
    elif (final_candidates & {"V", "V7"}) and bass_formula == "6-5" and key.mode == "minor":
        # Phrygian half cadence: iv6->V with bass b6->5 (semitone descent),
        # the standard minor-key half cadence.  Only in minor, where b6->5
        # is a half step; in major the same degree motion is a whole step
        # and lacks the Phrygian character.
        candidates.append("PHC")
    elif final_candidates & {"V", "V7"}:
        candidates.append("HC")
    elif _has_tonic_resolution(final_candidates) and _has_plagal_function(penultimate_candidates):
        # Plagal cadence: IV->I (the "Amen" cadence).
        candidates.append("PC")
    elif score >= 0.30:
        candidates.append("cadential")
    return score, evidence, candidates, bass_formula, soprano_formula


def detect_cadences(graph: EventGraph) -> list[Cadence]:
    key = graph.metadata.key_estimate
    if key is None:
        raise ValueError("Key estimate required")
    slices = build_verticalities(graph)
    events = summarize_harmony(graph)
    cadences: list[Cadence] = []
    seen_measures: set[int] = set()

    by_measure: dict[int, list[tuple[object, HarmonicEvent]]] = {}
    for slice_, event in zip(slices, events):
        by_measure.setdefault(slice_.measure_number, []).append((slice_, event))

    # Check measure boundaries
    measures = sorted(by_measure)
    for left_measure, right_measure in zip(measures, measures[1:]):
        prev_slice, penultimate = by_measure[left_measure][-1]
        final_slice, final = by_measure[right_measure][0]
        score, evidence, candidates, bass_formula, soprano_formula = _score_cadence_pair(
            prev_slice, final_slice, penultimate, final, key
        )
        if score >= 0.30 and candidates:
            seen_measures.add(right_measure)
            cadences.append(
                Cadence(
                    cadence_id=f"{graph.metadata.encoding_id}:cad:{right_measure}",
                    ref_id=f"{graph.metadata.encoding_id}:m{right_measure}",
                    cadence_type=candidates[0],
                    type_candidates=candidates,
                    key_before=f"{key.tonic} {key.mode}",
                    key_after=f"{key.tonic} {key.mode}",
                    bass_formula=bass_formula,
                    soprano_formula=soprano_formula,
                    strength=round(min(score, 0.99), 2),
                    voice_leading_evidence=evidence,
                    detector_confidence=round(min(score, 0.99), 2),
                )
            )

    # Also check at fermata locations within measures
    for i in range(1, len(slices)):
        final_slice = slices[i]
        if not any(note.fermata for note in final_slice.active_notes):
            continue
        if final_slice.measure_number in seen_measures:
            continue
        prev_slice = slices[i - 1]
        final_event = events[i]
        penultimate_event = events[i - 1]
        score, evidence, candidates, bass_formula, soprano_formula = _score_cadence_pair(
            prev_slice, final_slice, penultimate_event, final_event, key
        )
        if score >= 0.30 and candidates:
            m = final_slice.measure_number
            seen_measures.add(m)
            cadences.append(
                Cadence(
                    cadence_id=f"{graph.metadata.encoding_id}:cad:{m}:f",
                    ref_id=f"{graph.metadata.encoding_id}:m{m}",
                    cadence_type=candidates[0],
                    type_candidates=candidates,
                    key_before=f"{key.tonic} {key.mode}",
                    key_after=f"{key.tonic} {key.mode}",
                    bass_formula=bass_formula,
                    soprano_formula=soprano_formula,
                    strength=round(min(score, 0.99), 2),
                    voice_leading_evidence=evidence,
                    detector_confidence=round(min(score, 0.99), 2),
                )
            )

    cadences.sort(key=lambda c: int(c.ref_id.rsplit("m", 1)[-1]))
    return cadences
