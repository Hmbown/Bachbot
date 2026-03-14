from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from bachbot.exports.json_export import write_json
from bachbot.models.patterns import CorpusPatternIndex, PatternOccurrence, PatternStats
from bachbot.registry.storage import BachbotStorage

_MEASURE_REF_RE = re.compile(r":m(?P<measure>\d+)$")
_HARMONIC_EVENT_RE = re.compile(r":h(?P<measure>\d+):")


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _measure_number(ref_id: str, harmonic_event_id: str = "") -> int:
    match = _MEASURE_REF_RE.search(ref_id)
    if match:
        return int(match.group("measure"))
    match = _HARMONIC_EVENT_RE.search(harmonic_event_id)
    if match:
        return int(match.group("measure"))
    return 0


def _pattern_string(labels: Sequence[str]) -> str:
    return "-".join(labels)


def parse_pattern_query(pattern: str) -> tuple[str, ...]:
    if "-" in pattern:
        parts = pattern.split("-")
    else:
        parts = re.split(r"[\s,]+", pattern)
    return tuple(part.strip() for part in parts if part.strip())


def _percentile(values: Sequence[int], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return float(ordered[index])


def _load_bundle_paths(dataset: str) -> list[Path]:
    storage = BachbotStorage(dataset).ensure()
    index_path = Path(storage.derived_dir) / "analysis_index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Analysis index not found for dataset {dataset}: {index_path}")
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    bundle_paths: list[Path] = []
    for record in payload.get("analyses", []):
        bundle_path = Path(record["bundle_path"])
        if bundle_path.exists():
            bundle_paths.append(bundle_path)
    return bundle_paths


def load_corpus_bundles(dataset: str) -> list[dict]:
    bundles: list[dict] = []
    for bundle_path in _load_bundle_paths(dataset):
        bundles.append(json.loads(bundle_path.read_text(encoding="utf-8")))
    return bundles


def _extract_primary_roman_sequence(bundle: dict, collapse_repeats: bool = True) -> list[dict]:
    harmony = bundle.get("deterministic_findings", {}).get("harmony", [])
    ordered = sorted(
        harmony,
        key=lambda event: (
            float(event.get("onset", 0.0)),
            str(event.get("harmonic_event_id", "")),
            str(event.get("ref_id", "")),
        ),
    )
    sequence: list[dict] = []
    previous_label: str | None = None
    for event in ordered:
        candidates = event.get("roman_numeral_candidate_set") or []
        if not candidates:
            continue
        label = candidates[0]
        if collapse_repeats and previous_label == label:
            continue
        sequence.append(
            {
                "label": label,
                "ref_id": event.get("ref_id", ""),
                "harmonic_event_id": event.get("harmonic_event_id", ""),
                "measure": _measure_number(event.get("ref_id", ""), event.get("harmonic_event_id", "")),
                "onset": float(event.get("onset", 0.0)),
                "local_key": event.get("local_key"),
                "global_key": event.get("global_key"),
            }
        )
        previous_label = label
    return sequence


def _window_occurrence(bundle: dict, window: Sequence[dict]) -> PatternOccurrence:
    local_keys: list[str] = []
    for item in window:
        local_key = item.get("local_key")
        if local_key and local_key not in local_keys:
            local_keys.append(local_key)
    metadata = bundle.get("metadata", {})
    return PatternOccurrence(
        work_id=bundle.get("work_id", ""),
        encoding_id=metadata.get("encoding_id", bundle.get("work_id", "")),
        mode=metadata.get("key_mode", "unknown"),
        start_ref_id=window[0]["ref_id"],
        end_ref_id=window[-1]["ref_id"],
        start_measure=int(window[0]["measure"]),
        end_measure=int(window[-1]["measure"]),
        start_onset=float(window[0]["onset"]),
        end_onset=float(window[-1]["onset"]),
        global_key=window[0].get("global_key") or metadata.get("key"),
        local_keys=local_keys,
    )


def mine_patterns(
    corpus: Sequence[dict],
    *,
    ngram: int = 4,
    dataset_id: str = "unknown",
    mode: str | None = None,
    collapse_repeats: bool = True,
    min_count: int = 4,
    min_work_count: int = 4,
    min_pmi: float = 0.5,
    null_trials: int = 32,
) -> CorpusPatternIndex:
    if ngram < 2:
        raise ValueError("ngram must be at least 2")

    selected = [
        bundle
        for bundle in corpus
        if mode is None or bundle.get("metadata", {}).get("key_mode", "").lower() == mode.lower()
    ]

    unigram_counts: Counter[str] = Counter()
    pattern_counts: Counter[tuple[str, ...]] = Counter()
    occurrences_by_pattern: dict[tuple[str, ...], list[PatternOccurrence]] = defaultdict(list)
    work_ids_by_pattern: dict[tuple[str, ...], set[str]] = defaultdict(set)
    total_windows = 0
    sequences: list[tuple[dict, list[dict]]] = []

    for bundle in selected:
        sequence = _extract_primary_roman_sequence(bundle, collapse_repeats=collapse_repeats)
        sequences.append((bundle, sequence))
        labels = [item["label"] for item in sequence]
        unigram_counts.update(labels)
        if len(sequence) < ngram:
            continue
        for index in range(len(sequence) - ngram + 1):
            window = sequence[index : index + ngram]
            pattern = tuple(item["label"] for item in window)
            pattern_counts[pattern] += 1
            total_windows += 1
            occurrence = _window_occurrence(bundle, window)
            occurrences_by_pattern[pattern].append(occurrence)
            work_ids_by_pattern[pattern].add(occurrence.work_id)

    total_labels = sum(unigram_counts.values())
    null_count_samples: dict[tuple[str, ...], list[int]] = {pattern: [] for pattern in pattern_counts}
    null_work_samples: dict[tuple[str, ...], list[int]] = {pattern: [] for pattern in pattern_counts}
    if total_windows and total_labels and pattern_counts and null_trials > 0:
        vocabulary = tuple(unigram_counts.keys())
        weights = tuple(unigram_counts[label] for label in vocabulary)
        rng = random.Random(0)
        for _ in range(null_trials):
            trial_counts: Counter[tuple[str, ...]] = Counter()
            trial_work_ids: dict[tuple[str, ...], set[str]] = defaultdict(set)
            for bundle, sequence in sequences:
                if len(sequence) < ngram:
                    continue
                synthetic_labels = rng.choices(vocabulary, weights=weights, k=len(sequence))
                work_id = bundle.get("work_id", "")
                for index in range(len(synthetic_labels) - ngram + 1):
                    pattern = tuple(synthetic_labels[index : index + ngram])
                    trial_counts[pattern] += 1
                    trial_work_ids[pattern].add(work_id)
            for pattern in pattern_counts:
                null_count_samples[pattern].append(trial_counts.get(pattern, 0))
                null_work_samples[pattern].append(len(trial_work_ids.get(pattern, set())))

    summaries: list[PatternStats] = []
    for labels, count in pattern_counts.items():
        if total_windows == 0 or total_labels == 0:
            expected_count = 0.0
            pmi = 0.0
        else:
            expected_probability = 1.0
            for label in labels:
                expected_probability *= unigram_counts[label] / total_labels
            observed_probability = count / total_windows
            expected_count = total_windows * expected_probability
            if observed_probability > 0 and expected_probability > 0:
                pmi = math.log2(observed_probability / expected_probability)
            else:
                pmi = 0.0
        work_count = len(work_ids_by_pattern[labels])
        null_counts = null_count_samples.get(labels, [])
        null_works = null_work_samples.get(labels, [])
        null_mean_count = (sum(null_counts) / len(null_counts)) if null_counts else 0.0
        null_p95_count = _percentile(null_counts, 0.95)
        null_mean_work_count = (sum(null_works) / len(null_works)) if null_works else 0.0
        null_p95_work_count = _percentile(null_works, 0.95)
        count_lift = count / max(null_mean_count, 1e-6)
        work_lift = work_count / max(null_mean_work_count, 1e-6)
        significant = (
            count >= min_count
            and work_count >= min_work_count
            and pmi >= min_pmi
            and count > max(expected_count, null_p95_count)
            and work_count > null_p95_work_count
            and (count_lift >= 1.5 or work_lift >= 1.5)
        )
        summaries.append(
            PatternStats(
                pattern_id=f"{ngram}:{'|'.join(labels)}",
                ngram=ngram,
                pattern=_pattern_string(labels),
                labels=list(labels),
                count=count,
                work_count=work_count,
                support=round(count / total_windows, 4) if total_windows else 0.0,
                expected_count=round(expected_count, 4),
                pmi=round(pmi, 4),
                null_mean_count=round(null_mean_count, 4),
                null_p95_count=round(null_p95_count, 4),
                null_mean_work_count=round(null_mean_work_count, 4),
                null_p95_work_count=round(null_p95_work_count, 4),
                significant=significant,
                occurrences=occurrences_by_pattern[labels],
            )
        )

    summaries.sort(
        key=lambda summary: (
            -summary.count,
            -summary.work_count,
            -summary.pmi,
            summary.pattern,
        )
    )
    return CorpusPatternIndex(
        dataset_id=dataset_id,
        ngram=ngram,
        corpus_size=len(selected),
        total_windows=total_windows,
        label_vocabulary_size=len(unigram_counts),
        generated_at=_timestamp(),
        patterns=summaries,
    )


def filter_patterns(
    index: CorpusPatternIndex,
    *,
    pattern: str | None = None,
    significant_only: bool = False,
) -> list[PatternStats]:
    patterns = index.patterns
    if significant_only:
        patterns = [summary for summary in patterns if summary.significant]
    if pattern is not None:
        target = parse_pattern_query(pattern)
        patterns = [summary for summary in patterns if tuple(summary.labels) == target]
    return patterns


def pattern_index_output_path(dataset: str, ngram: int) -> Path:
    storage = BachbotStorage(dataset).ensure()
    return Path(storage.derived_dir) / f"pattern_index.{ngram}gram.json"


def mine_dataset_patterns(
    *,
    dataset: str = "dcml_bach_chorales",
    ngram: int = 4,
    mode: str | None = None,
    output: Path | None = None,
    min_count: int = 4,
    min_work_count: int = 4,
    min_pmi: float = 0.5,
    null_trials: int = 32,
) -> tuple[CorpusPatternIndex, Path]:
    bundles = load_corpus_bundles(dataset)
    index = mine_patterns(
        bundles,
        ngram=ngram,
        dataset_id=dataset,
        mode=mode,
        min_count=min_count,
        min_work_count=min_work_count,
        min_pmi=min_pmi,
        null_trials=null_trials,
    )
    output_path = output or pattern_index_output_path(dataset, ngram)
    write_json(index.model_dump(mode="json"), output_path)
    return index, output_path
