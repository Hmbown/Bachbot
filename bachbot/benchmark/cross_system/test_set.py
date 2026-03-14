"""Standard test set of soprano melodies for cross-system comparison."""

from __future__ import annotations

import json
from pathlib import Path

from bachbot.models.base import BachbotModel

# ── Test melody model ────────────────────────────────────────────────

class BenchmarkMelody(BachbotModel):
    """A soprano melody extracted from the corpus for cross-system benchmarking."""

    melody_id: str
    title: str
    soprano_midi: list[int]
    key: str
    mode: str
    meter: str
    beats_per_note: float = 1.0
    ground_truth_work_id: str | None = None


# Number of melodies in the standard test set.
STANDARD_30_COUNT = 30

# ── Corpus paths ─────────────────────────────────────────────────────

_CORPUS_NORM = Path("data/normalized/dcml_bach_chorales")
_CORPUS_DERIVED = Path("data/derived/dcml_bach_chorales")

# Voice ID candidates for soprano (corpus uses short IDs).
_SOPRANO_CANDIDATES = ("Soprano:1", "S", "soprano", "Soprano")


def _extract_soprano_midi(graph_data: dict) -> list[int]:
    """Extract ordered soprano MIDI pitches from a raw event-graph dict."""
    notes = graph_data.get("notes", [])
    by_voice: dict[str, list[dict]] = {}
    for n in notes:
        by_voice.setdefault(n["voice_id"], []).append(n)

    vid: str | None = None
    for candidate in _SOPRANO_CANDIDATES:
        if candidate in by_voice and by_voice[candidate]:
            vid = candidate
            break
    if vid is None:
        return []

    soprano = [
        n for n in by_voice[vid]
        if n.get("midi") is not None and not n.get("is_rest", False)
    ]
    soprano.sort(key=lambda n: n["offset_quarters"])
    return [n["midi"] for n in soprano]


def _infer_beats_per_note(graph_data: dict, soprano_voice_id: str) -> float:
    """Estimate beats per note from median soprano duration."""
    notes = [
        n for n in graph_data.get("notes", [])
        if n["voice_id"] == soprano_voice_id
        and n.get("midi") is not None
        and not n.get("is_rest", False)
    ]
    if not notes:
        return 1.0
    durations = sorted(n["duration_quarters"] for n in notes)
    mid = len(durations) // 2
    return durations[mid] if durations else 1.0


def build_standard_test_set(limit: int = STANDARD_30_COUNT) -> list[BenchmarkMelody]:
    """Build the standard test set by extracting soprano lines from the corpus.

    Falls back to a synthetic test set when the corpus is unavailable.

    Parameters
    ----------
    limit : int
        Maximum number of melodies to include (default 30).
    """
    melodies: list[BenchmarkMelody] = []

    graph_paths = sorted(_CORPUS_NORM.glob("*.event_graph.json"))
    if not graph_paths:
        return _synthetic_fallback(limit)

    # Spread evenly across corpus
    step = max(1, len(graph_paths) // limit)
    selected = graph_paths[::step][:limit]

    for gp in selected:
        stem = gp.name.replace(".event_graph.json", "")
        try:
            graph_data = json.loads(gp.read_text(encoding="utf-8"))
        except Exception:
            continue

        midi_seq = _extract_soprano_midi(graph_data)
        if not midi_seq:
            continue

        meta = graph_data.get("metadata", {})
        key_est = meta.get("key_estimate", {})
        work_id = meta.get("work_id", stem)
        title = meta.get("title", stem)
        tonic = key_est.get("tonic", "C")
        mode = key_est.get("mode", "major")
        meter = meta.get("meter", "4/4")

        # Determine voice id used
        vid = None
        for candidate in _SOPRANO_CANDIDATES:
            found = [n for n in graph_data["notes"] if n["voice_id"] == candidate and n.get("midi")]
            if found:
                vid = candidate
                break
        bpn = _infer_beats_per_note(graph_data, vid) if vid else 1.0

        melodies.append(BenchmarkMelody(
            melody_id=f"std30:{work_id}",
            title=title,
            soprano_midi=midi_seq,
            key=tonic,
            mode=mode,
            meter=meter,
            beats_per_note=bpn,
            ground_truth_work_id=work_id,
        ))

    return melodies


def _synthetic_fallback(limit: int) -> list[BenchmarkMelody]:
    """Generate simple synthetic soprano melodies when no corpus is available."""
    # C major scale-based melodies for testing without corpus.
    base_melodies: list[list[int]] = [
        [60, 62, 64, 65, 67, 65, 64, 62, 60],                    # scale up/down
        [67, 65, 64, 62, 60, 62, 64, 65, 67],                    # scale down/up
        [60, 64, 67, 72, 71, 67, 64, 60],                        # arpeggio
        [72, 71, 69, 67, 65, 64, 62, 60],                        # descending scale
        [60, 60, 62, 64, 64, 62, 60, 59, 60],                    # simple phrase
        [65, 64, 62, 60, 62, 64, 65, 67, 65],                    # F-centered
        [67, 69, 71, 72, 71, 69, 67, 65, 64, 62, 60],            # G arch
        [60, 62, 64, 62, 60, 64, 67, 64, 60],                    # triadic
        [72, 69, 67, 65, 64, 62, 64, 67, 72],                    # bowl shape
        [60, 64, 62, 65, 64, 67, 65, 69, 67, 72],                # ascending thirds
    ]
    result: list[BenchmarkMelody] = []
    for i in range(min(limit, len(base_melodies))):
        result.append(BenchmarkMelody(
            melody_id=f"synthetic:{i + 1}",
            title=f"Synthetic melody {i + 1}",
            soprano_midi=base_melodies[i],
            key="C",
            mode="major",
            meter="4/4",
            beats_per_note=1.0,
            ground_truth_work_id=None,
        ))
    # If more are requested than base melodies, transpose existing ones.
    idx = len(base_melodies)
    while len(result) < limit and idx < limit:
        base = base_melodies[idx % len(base_melodies)]
        transpose = (idx // len(base_melodies)) * 2  # up a whole step each cycle
        result.append(BenchmarkMelody(
            melody_id=f"synthetic:{idx + 1}",
            title=f"Synthetic melody {idx + 1}",
            soprano_midi=[p + transpose for p in base],
            key="C",
            mode="major",
            meter="4/4",
            beats_per_note=1.0,
            ground_truth_work_id=None,
        ))
        idx += 1
    return result
