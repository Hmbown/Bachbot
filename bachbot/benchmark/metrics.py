"""Shared metric functions for BachBench. No external ML deps — stdlib math only."""

from __future__ import annotations

import math
from collections import Counter

from bachbot.benchmark.protocol import VOICE_NORMALIZE, extract_voice_notes
from bachbot.composition.validators.hard_rules import validate_graph
from bachbot.encodings.event_graph import EventGraph


def pitch_accuracy(predicted: EventGraph, ground_truth: EventGraph, voices: list[str] | None = None) -> float:
    """Fraction of notes with correct MIDI pitch, aligned by (onset, normalized_voice)."""
    gt_map: dict[tuple[float, str], int] = {}
    for n in ground_truth.notes:
        if n.midi is None or n.is_rest:
            continue
        role = VOICE_NORMALIZE.get(n.voice_id, n.voice_id)
        if voices and role not in voices:
            continue
        gt_map[(round(n.offset_quarters, 4), role)] = n.midi

    if not gt_map:
        return 0.0

    correct = 0
    for n in predicted.notes:
        if n.midi is None or n.is_rest:
            continue
        role = VOICE_NORMALIZE.get(n.voice_id, n.voice_id)
        if voices and role not in voices:
            continue
        key = (round(n.offset_quarters, 4), role)
        if key in gt_map and gt_map[key] == n.midi:
            correct += 1

    return correct / len(gt_map)


def voice_leading_score(graph: EventGraph) -> float:
    """1.0 minus normalized count of parallel 5ths/8ves violations."""
    report = validate_graph(graph)
    parallel_count = sum(
        1 for i in report.issues
        if i.code in ("parallel_5ths", "parallel_8ves")
    )
    total_notes = len([n for n in graph.notes if n.midi is not None and not n.is_rest])
    if total_notes < 2:
        return 1.0
    return max(0.0, 1.0 - parallel_count / (total_notes / 4))


def harmonic_similarity(predicted: EventGraph, ground_truth: EventGraph) -> float:
    """Cosine similarity of pitch-class histograms."""
    def _pc_hist(g: EventGraph) -> list[int]:
        hist = [0] * 12
        for n in g.notes:
            if n.midi is not None and not n.is_rest:
                hist[n.midi % 12] += 1
        return hist

    p = _pc_hist(predicted)
    q = _pc_hist(ground_truth)
    return cosine_sim(p, q)


def rhythm_accuracy(predicted: EventGraph, ground_truth: EventGraph) -> float:
    """Fraction of notes with correct duration, aligned by (onset, voice)."""
    gt_map: dict[tuple[float, str], float] = {}
    for n in ground_truth.notes:
        if n.midi is None or n.is_rest:
            continue
        role = VOICE_NORMALIZE.get(n.voice_id, n.voice_id)
        gt_map[(round(n.offset_quarters, 4), role)] = n.duration_quarters

    if not gt_map:
        return 0.0

    correct = 0
    for n in predicted.notes:
        if n.midi is None or n.is_rest:
            continue
        role = VOICE_NORMALIZE.get(n.voice_id, n.voice_id)
        key = (round(n.offset_quarters, 4), role)
        if key in gt_map and abs(gt_map[key] - n.duration_quarters) < 0.01:
            correct += 1

    return correct / len(gt_map)


def validation_pass_rate(graph: EventGraph) -> float:
    """1.0 if validate_graph passes, 0.0 otherwise."""
    return 1.0 if validate_graph(graph).passed else 0.0


def chord_variety_ratio(predicted_chords: list[str], ground_truth_chords: list[str]) -> float:
    """Ratio of unique chord count: predicted / ground_truth."""
    gt_variety = len(set(ground_truth_chords))
    if gt_variety == 0:
        return 0.0
    return min(1.0, len(set(predicted_chords)) / gt_variety)


def cadence_f1(predicted_measures: list[int], ground_truth_measures: list[int]) -> float:
    """F1 score of cadence measure predictions."""
    pred_set = set(predicted_measures)
    gt_set = set(ground_truth_measures)
    if not gt_set and not pred_set:
        return 1.0
    if not gt_set or not pred_set:
        return 0.0
    tp = len(pred_set & gt_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(gt_set) if gt_set else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def pitch_class_entropy(graph: EventGraph) -> float:
    """Shannon entropy of pitch class histogram."""
    hist = [0] * 12
    for n in graph.notes:
        if n.midi is not None and not n.is_rest:
            hist[n.midi % 12] += 1
    return _entropy(hist)


def stepwise_fraction(graph: EventGraph, role: str) -> float:
    """Fraction of successive intervals that are stepwise (≤2 semitones)."""
    notes = extract_voice_notes(graph, role)
    midis = [n.midi for n in notes if n.midi is not None]
    if len(midis) < 2:
        return 0.0
    steps = sum(1 for a, b in zip(midis, midis[1:]) if abs(b - a) <= 2)
    return steps / (len(midis) - 1)


def cosine_sim(a: list[float | int], b: list[float | int]) -> float:
    """Manual cosine similarity."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    return -sum(
        (c / total) * math.log2(c / total)
        for c in counts if c > 0
    )
