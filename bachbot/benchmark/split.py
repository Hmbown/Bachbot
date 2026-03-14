"""Deterministic split helpers for BachBench."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from bachbot.benchmark.protocol import extract_voice_notes
from bachbot.encodings.event_graph import EventGraph

_WORK_ID_PREFIX = re.compile(r"notes__(\d+)")


def compute_split(encoding_ids: list[str], test_fraction: int = 5) -> dict[str, str]:
    """Deterministic hash-based split. test_fraction=5 means ~20% test.

    Each ID's assignment depends only on its own hash, so the split is
    stable when chorales are added or removed.
    """
    result: dict[str, str] = {}
    for eid in encoding_ids:
        h = hashlib.sha256(eid.encode()).hexdigest()
        bucket = int(h[-2:], 16) % test_fraction
        result[eid] = "test" if bucket == 0 else "train"
    return result


def melody_signature(graph: EventGraph) -> str:
    """Return a stable hash for the soprano melody shape.

    The signature uses soprano MIDI and duration pairs so duplicated chorale
    tunes stay in the same corpus partition.
    """

    soprano = extract_voice_notes(graph, "soprano")
    payload = tuple((note.midi, round(note.duration_quarters, 4)) for note in soprano)
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()


def corpus_order_key(work_id: str) -> tuple[int, str]:
    """Sort Bach chorales by their corpus index when available."""

    match = _WORK_ID_PREFIX.search(work_id)
    prefix = int(match.group(1)) if match else 10**9
    return prefix, work_id


def compute_grouped_split(
    graphs: list[EventGraph],
    *,
    train_fraction: int = 70,
    val_fraction: int = 15,
    test_fraction: int = 15,
) -> dict[str, str]:
    """Assign train/val/test splits while keeping duplicate melodies together."""

    if train_fraction + val_fraction + test_fraction != 100:
        raise ValueError("train_fraction + val_fraction + test_fraction must equal 100")

    groups: dict[str, list[str]] = defaultdict(list)
    for graph in graphs:
        groups[melody_signature(graph)].append(graph.work_id)

    ordered_groups = sorted(
        groups.values(),
        key=lambda group: min(corpus_order_key(work_id) for work_id in group),
    )
    total = sum(len(group) for group in ordered_groups)
    if total == 0:
        return {}

    train_target = total * train_fraction / 100
    val_target = total * val_fraction / 100
    result: dict[str, str] = {}
    counts = {"train": 0, "val": 0, "test": 0}

    for group in ordered_groups:
        if counts["train"] < train_target:
            bucket = "train"
        elif counts["val"] < val_target:
            bucket = "val"
        else:
            bucket = "test"
        for work_id in group:
            result[work_id] = bucket
            counts[bucket] += 1

    return result


def load_split_manifest(path: Path) -> dict[str, str]:
    """Load cached split from JSON manifest."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_split_manifest(split: dict[str, str], path: Path) -> None:
    """Cache split to data/manifests/bachbench_split.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(split, indent=2, sort_keys=True), encoding="utf-8")
