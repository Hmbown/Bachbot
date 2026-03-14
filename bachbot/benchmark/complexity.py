"""Information-theoretic complexity metrics for chorales and generated studies."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from bachbot.analysis.harmony.cadence import summarize_harmony
from bachbot.benchmark.protocol import extract_voice_notes
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import BachbotModel

DEFAULT_COMPLEXITY_STATS_PATH = Path("data/derived/complexity_corpus_stats.json")

_NOTE_TO_PC = {
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
_FIFTHS_POS = {pc: (pc * 7) % 12 for pc in range(12)}
_SCALAR_FIELDS = (
    "harmonic_entropy",
    "melodic_information_content",
    "voice_leading_mutual_information",
    "pitch_lz_complexity",
    "rhythm_lz_complexity",
    "average_tonal_tension",
    "peak_tonal_tension",
)


class TonalTensionPoint(BachbotModel):
    onset: float
    measure_number: int
    tension: float


class ComplexityProfile(BachbotModel):
    work_id: str
    harmonic_entropy: float
    melodic_information_content: float
    voice_leading_mutual_information: float
    pitch_lz_complexity: float
    rhythm_lz_complexity: float
    average_tonal_tension: float
    peak_tonal_tension: float
    tonal_tension_curve: list[TonalTensionPoint]


class MetricSummary(BachbotModel):
    mean: float
    std: float


class ComplexityCorpusStats(BachbotModel):
    graph_count: int
    metrics: dict[str, MetricSummary]


class ComplexityComparison(BachbotModel):
    z_scores: dict[str, float]
    divergence: float


def compute_complexity(graph: EventGraph) -> ComplexityProfile:
    """Compute scalar complexity metrics plus a tonal-tension time series."""

    harmony = summarize_harmony(graph)
    chord_labels = [
        event.roman_numeral_candidate_set[0]
        for event in harmony
        if event.roman_numeral_candidate_set
    ]
    melodic_notes = extract_voice_notes(graph, "soprano")
    if not melodic_notes:
        melodic_notes = graph.pitch_events()
    pitch_sequence = [note.midi % 12 for note in graph.pitch_events() if note.midi is not None]
    rhythm_sequence = [round(note.duration_quarters, 4) for note in graph.pitch_events() if note.midi is not None]
    melodic_sequence = [note.midi % 12 for note in melodic_notes if note.midi is not None]
    tonal_curve = _tonal_tension_curve(graph)
    tension_values = [point.tension for point in tonal_curve]

    return ComplexityProfile(
        work_id=graph.work_id,
        harmonic_entropy=round(_entropy(chord_labels), 4),
        melodic_information_content=round(_average_bigram_surprisal(melodic_sequence), 4),
        voice_leading_mutual_information=round(_voice_leading_mutual_information(graph), 4),
        pitch_lz_complexity=round(_lz_complexity_ratio(pitch_sequence), 4),
        rhythm_lz_complexity=round(_lz_complexity_ratio(rhythm_sequence), 4),
        average_tonal_tension=round(_mean(tension_values), 4),
        peak_tonal_tension=round(max(tension_values, default=0.0), 4),
        tonal_tension_curve=tonal_curve,
    )


def compute_corpus_complexity_stats(graphs: list[EventGraph]) -> ComplexityCorpusStats:
    profiles = [compute_complexity(graph) for graph in graphs]
    metrics: dict[str, MetricSummary] = {}
    for field in _SCALAR_FIELDS:
        values = [getattr(profile, field) for profile in profiles]
        metrics[field] = MetricSummary(
            mean=round(_mean(values), 4),
            std=round(_stddev(values), 4),
        )
    return ComplexityCorpusStats(graph_count=len(profiles), metrics=metrics)


def compare_profile_to_corpus(
    profile: ComplexityProfile,
    corpus_stats: ComplexityCorpusStats,
) -> ComplexityComparison:
    z_scores: dict[str, float] = {}
    for field in _SCALAR_FIELDS:
        summary = corpus_stats.metrics.get(field)
        value = getattr(profile, field)
        if summary is None or summary.std == 0:
            z_scores[field] = 0.0
            continue
        z_scores[field] = round((value - summary.mean) / summary.std, 4)
    return ComplexityComparison(
        z_scores=z_scores,
        divergence=complexity_divergence(profile, profile, corpus_stats=corpus_stats, z_scores_override=z_scores),
    )


def complexity_divergence(
    left: ComplexityProfile,
    right: ComplexityProfile,
    *,
    corpus_stats: ComplexityCorpusStats,
    z_scores_override: dict[str, float] | None = None,
) -> float:
    """Return the mean normalized distance across scalar complexity metrics."""

    distances: list[float] = []
    for field in _SCALAR_FIELDS:
        summary = corpus_stats.metrics.get(field)
        scale = summary.std if summary and summary.std > 0 else 1.0
        if z_scores_override is not None and left is right:
            distances.append(abs(z_scores_override.get(field, 0.0)))
        else:
            distances.append(abs(getattr(left, field) - getattr(right, field)) / scale)
    return round(_mean(distances), 4)


def load_or_compute_corpus_stats(
    graphs: list[EventGraph],
    *,
    output: Path = DEFAULT_COMPLEXITY_STATS_PATH,
) -> ComplexityCorpusStats:
    if output.exists():
        try:
            loaded = ComplexityCorpusStats.model_validate(json.loads(output.read_text(encoding="utf-8")))
            if loaded.graph_count == len(graphs):
                return loaded
        except (json.JSONDecodeError, ValueError):
            pass

    stats = compute_corpus_complexity_stats(graphs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(stats.model_dump(mode="json"), indent=2), encoding="utf-8")
    return stats


def _entropy(items: list[str]) -> float:
    counts = Counter(items)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in counts.values() if count)


def _average_bigram_surprisal(sequence: list[int]) -> float:
    if len(sequence) < 2:
        return 0.0
    vocab = set(sequence)
    unigram = Counter(sequence[:-1])
    bigram = Counter(zip(sequence, sequence[1:]))
    surprisals = []
    for left, right in zip(sequence, sequence[1:]):
        probability = (bigram[(left, right)] + 1) / (unigram[left] + len(vocab))
        surprisals.append(-math.log2(probability))
    return _mean(surprisals)


def _voice_leading_mutual_information(graph: EventGraph) -> float:
    adjacent_pairs = (("soprano", "alto"), ("alto", "tenor"), ("tenor", "bass"))
    by_role = {role: extract_voice_notes(graph, role) for role in ("soprano", "alto", "tenor", "bass")}
    voiced_onsets: dict[str, dict[float, int]] = {}
    for role, notes in by_role.items():
        voiced_onsets[role] = {note.offset_quarters: note.midi % 12 for note in notes if note.midi is not None}

    pair_scores: list[float] = []
    for left_role, right_role in adjacent_pairs:
        shared_onsets = sorted(set(voiced_onsets[left_role]) & set(voiced_onsets[right_role]))
        if len(shared_onsets) < 2:
            continue
        left_values = [voiced_onsets[left_role][onset] for onset in shared_onsets]
        right_values = [voiced_onsets[right_role][onset] for onset in shared_onsets]
        pair_scores.append(_mutual_information(left_values, right_values))
    return _mean(pair_scores)


def _mutual_information(left: list[int], right: list[int]) -> float:
    total = len(left)
    if total == 0:
        return 0.0
    joint = Counter(zip(left, right))
    left_counts = Counter(left)
    right_counts = Counter(right)
    info = 0.0
    for (left_value, right_value), count in joint.items():
        p_xy = count / total
        p_x = left_counts[left_value] / total
        p_y = right_counts[right_value] / total
        info += p_xy * math.log2(p_xy / (p_x * p_y))
    return info


def _lz_complexity_ratio(sequence: list[int | float]) -> float:
    if not sequence:
        return 0.0
    tokens = tuple(str(item) for item in sequence)
    phrases = 0
    index = 0
    seen: set[tuple[str, ...]] = set()
    while index < len(tokens):
        end = index + 1
        while end <= len(tokens) and tokens[index:end] in seen:
            end += 1
        phrase = tokens[index:min(end, len(tokens))]
        seen.add(phrase)
        phrases += 1
        index += len(phrase)
    return phrases / len(tokens)


def _tonal_tension_curve(graph: EventGraph) -> list[TonalTensionPoint]:
    tonic_pc = _tonic_pitch_class(graph)
    curve: list[TonalTensionPoint] = []
    for onset in graph.iter_onsets():
        active = [note for note in graph.active_pitches_at(onset) if note.midi is not None]
        if not active:
            continue
        distances = [_fifths_distance(note.midi % 12, tonic_pc) / 6 for note in active]
        curve.append(
            TonalTensionPoint(
                onset=round(onset, 4),
                measure_number=min(note.measure_number for note in active),
                tension=round(_mean(distances), 4),
            )
        )
    return curve


def _tonic_pitch_class(graph: EventGraph) -> int:
    key = graph.metadata.key_estimate
    if key is None:
        return 0
    return _NOTE_TO_PC.get(key.tonic, 0)


def _fifths_distance(left_pc: int, right_pc: int) -> int:
    left = _FIFTHS_POS[left_pc]
    right = _FIFTHS_POS[right_pc]
    diff = abs(left - right)
    return min(diff, 12 - diff)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)
