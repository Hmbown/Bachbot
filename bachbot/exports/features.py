"""Feature extraction from EvidenceBundle + EventGraph for ML datasets.

Produces a flat dict of 50+ features per chorale, suitable for tabular ML,
HuggingFace Datasets, or CSV export.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from bachbot.claims.bundle import EvidenceBundle
from bachbot.encodings.event_graph import EventGraph

# ── Feature catalog ──────────────────────────────────────────────────────
# Each entry: (feature_name, description, category)
FEATURE_CATALOG: list[tuple[str, str, str]] = [
    # Identity
    ("work_id", "Work identifier", "identity"),
    ("key_tonic_pc", "Key tonic as pitch class 0-11", "identity"),
    ("key_mode", "0=major, 1=minor", "identity"),
    # Structural
    ("measure_count", "Number of measures", "structural"),
    ("voice_count", "Number of voices", "structural"),
    ("total_duration_quarters", "Total duration in quarter notes", "structural"),
    ("note_count", "Total pitched notes", "structural"),
    ("phrase_count", "Number of phrase endings", "structural"),
    # Harmonic
    ("harmonic_event_count", "Total harmonic analysis events", "harmonic"),
    ("chord_variety", "Distinct chord labels used", "harmonic"),
    ("seventh_chord_ratio", "Fraction of chords that are sevenths", "harmonic"),
    ("modulation_count", "Distinct local keys", "harmonic"),
    ("dominant_ratio", "V+V7 as fraction of all chords", "harmonic"),
    ("tonic_ratio", "I/i as fraction of all chords", "harmonic"),
    ("subdominant_ratio", "IV/iv as fraction of all chords", "harmonic"),
    ("chord_freq_I", "Frequency of I", "harmonic"),
    ("chord_freq_V", "Frequency of V", "harmonic"),
    ("chord_freq_IV", "Frequency of IV", "harmonic"),
    ("chord_freq_ii", "Frequency of ii", "harmonic"),
    ("chord_freq_vi", "Frequency of vi", "harmonic"),
    ("chord_freq_V7", "Frequency of V7", "harmonic"),
    ("chord_freq_iii", "Frequency of iii", "harmonic"),
    ("chord_freq_viio", "Frequency of vii-dim", "harmonic"),
    ("progression_bigram_count", "Distinct chord-to-chord transitions", "harmonic"),
    # Cadences
    ("cadence_count", "Total cadences detected", "cadence"),
    ("cadence_PAC", "Perfect authentic cadences", "cadence"),
    ("cadence_IAC", "Imperfect authentic cadences", "cadence"),
    ("cadence_HC", "Half cadences", "cadence"),
    ("cadence_DC", "Deceptive cadences", "cadence"),
    # Voice leading
    ("parallel_5ths", "Parallel fifths count", "voice_leading"),
    ("parallel_8ves", "Parallel octaves count", "voice_leading"),
    ("voice_crossings", "Voice crossing count", "voice_leading"),
    ("contrary_motion", "Contrary motion count", "voice_leading"),
    ("similar_motion", "Similar motion count", "voice_leading"),
    ("oblique_motion", "Oblique motion count", "voice_leading"),
    ("parallel_motion", "Parallel motion count", "voice_leading"),
    ("suspension_count", "Detected suspensions", "voice_leading"),
    ("spacing_violations", "SATB spacing violations", "voice_leading"),
    ("range_violations", "SATB range violations", "voice_leading"),
    # Melodic (per-voice stepwise motion %)
    ("stepwise_soprano", "Soprano stepwise motion fraction", "melodic"),
    ("stepwise_alto", "Alto stepwise motion fraction", "melodic"),
    ("stepwise_tenor", "Tenor stepwise motion fraction", "melodic"),
    ("stepwise_bass", "Bass stepwise motion fraction", "melodic"),
    ("leap_soprano", "Soprano leaps (>2 semitones) fraction", "melodic"),
    ("leap_bass", "Bass leaps fraction", "melodic"),
    ("range_soprano", "Soprano pitch range in semitones", "melodic"),
    ("range_alto", "Alto pitch range in semitones", "melodic"),
    ("range_tenor", "Tenor pitch range in semitones", "melodic"),
    ("range_bass", "Bass pitch range in semitones", "melodic"),
    # Rhythmic
    ("onset_count", "Total unique note onsets", "rhythmic"),
    ("onset_density_mean", "Average onsets per measure", "rhythmic"),
    ("harmonic_rhythm_mean", "Average chord changes per measure", "rhythmic"),
    # Distribution
    ("pitch_class_entropy", "Shannon entropy of pitch class histogram", "distribution"),
    ("pitch_class_0", "C pitch class count", "distribution"),
    ("pitch_class_1", "C#/Db count", "distribution"),
    ("pitch_class_2", "D count", "distribution"),
    ("pitch_class_3", "D#/Eb count", "distribution"),
    ("pitch_class_4", "E count", "distribution"),
    ("pitch_class_5", "F count", "distribution"),
    ("pitch_class_6", "F#/Gb count", "distribution"),
    ("pitch_class_7", "G count", "distribution"),
    ("pitch_class_8", "G#/Ab count", "distribution"),
    ("pitch_class_9", "A count", "distribution"),
    ("pitch_class_10", "A#/Bb count", "distribution"),
    ("pitch_class_11", "B count", "distribution"),
]

_NOTE_TO_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
_SEVENTH_LABELS = {"V7", "viiø7", "viio7", "ii7", "IV7", "vi7", "iv7", "VI7", "iiø7"}

# Voice ID candidates — composition uses "Soprano:1", corpus uses "S", etc.
_VOICE_CANDIDATES: dict[str, list[str]] = {
    "soprano": ["Soprano:1", "S", "soprano", "Soprano"],
    "alto": ["Alto:1", "A", "alto", "Alto"],
    "tenor": ["Tenor:1", "T", "tenor", "Tenor"],
    "bass": ["Bass:1", "B", "bass", "Bass"],
}


def _resolve_voice_id(by_voice: dict[str, list], role: str) -> str | None:
    """Find the first matching voice ID for a role."""
    for candidate in _VOICE_CANDIDATES.get(role, []):
        if candidate in by_voice and by_voice[candidate]:
            return candidate
    return None


def _safe_div(a: float, b: float) -> float:
    return a / b if b > 0 else 0.0


def _stepwise_fraction(midis: list[int]) -> float:
    if len(midis) < 2:
        return 0.0
    steps = sum(1 for a, b in zip(midis, midis[1:]) if abs(b - a) <= 2)
    return steps / (len(midis) - 1)


def _leap_fraction(midis: list[int]) -> float:
    if len(midis) < 2:
        return 0.0
    leaps = sum(1 for a, b in zip(midis, midis[1:]) if abs(b - a) > 2)
    return leaps / (len(midis) - 1)


def _entropy(counts: list[int]) -> float:
    import math
    total = sum(counts)
    if total == 0:
        return 0.0
    return -sum(
        (c / total) * math.log2(c / total)
        for c in counts if c > 0
    )


def extract_features(bundle: dict, graph: EventGraph | None = None) -> dict[str, float | int | str]:
    """Extract 50+ features from an evidence bundle and optional EventGraph.

    Parameters
    ----------
    bundle : dict
        Evidence bundle (model_dump output or raw JSON).
    graph : EventGraph, optional
        Source event graph for raw note-level features.
        If None, note-level and melodic features are omitted.

    Returns
    -------
    dict[str, float | int | str]
        Flat feature dict suitable for tabular export.
    """
    findings = bundle.get("deterministic_findings", {})
    metadata = bundle.get("metadata", {})
    harmony = findings.get("harmony", [])
    cadences = findings.get("cadences", [])
    phrase_endings = findings.get("phrase_endings", [])
    vl = findings.get("voice_leading", {})
    counterpoint = vl.get("counterpoint", {})
    distributions = findings.get("distributions", {})

    features: dict[str, float | int | str] = {}

    # ── Identity ──
    features["work_id"] = bundle.get("work_id", "")
    tonic_str = metadata.get("key_tonic", "C")
    features["key_tonic_pc"] = _NOTE_TO_PC.get(tonic_str, 0)
    features["key_mode"] = 0 if metadata.get("key_mode", "major") == "major" else 1

    # ── Structural ──
    passage_refs = bundle.get("passage_refs", [])
    if passage_refs:
        measures = [r.get("measure_number_logical", r.get("measure_number_notated", 0)) for r in passage_refs]
        features["measure_count"] = max(measures) if measures else 0
    else:
        features["measure_count"] = 0
    features["voice_count"] = len({v for r in passage_refs for v in r.get("voice_ids", [])}) if passage_refs else 4
    features["phrase_count"] = len(phrase_endings)

    # ── Harmonic ──
    chord_counts: Counter = Counter()
    for h in harmony:
        candidates = h.get("roman_numeral_candidate_set", [])
        if candidates:
            chord_counts[candidates[0]] += 1

    total_chords = sum(chord_counts.values())
    features["harmonic_event_count"] = total_chords
    features["chord_variety"] = len(chord_counts)
    features["seventh_chord_ratio"] = round(_safe_div(
        sum(chord_counts.get(s, 0) for s in _SEVENTH_LABELS), total_chords
    ), 4)

    # Local keys / modulation
    local_keys = {h.get("local_key", "") for h in harmony if h.get("local_key")}
    features["modulation_count"] = len(local_keys)

    # Functional ratios
    dom_count = chord_counts.get("V", 0) + chord_counts.get("V7", 0)
    features["dominant_ratio"] = round(_safe_div(dom_count, total_chords), 4)
    tonic_count = chord_counts.get("I", 0) + chord_counts.get("i", 0)
    features["tonic_ratio"] = round(_safe_div(tonic_count, total_chords), 4)
    subdom_count = chord_counts.get("IV", 0) + chord_counts.get("iv", 0)
    features["subdominant_ratio"] = round(_safe_div(subdom_count, total_chords), 4)

    # Individual chord frequencies
    for label in ["I", "V", "IV", "ii", "vi", "V7", "iii"]:
        features[f"chord_freq_{label}"] = chord_counts.get(label, 0)
    features["chord_freq_viio"] = chord_counts.get("vii°", 0) + chord_counts.get("viio7", 0)

    # Progression bigrams
    chord_labels = [h.get("roman_numeral_candidate_set", [""])[0] for h in harmony if h.get("roman_numeral_candidate_set")]
    bigrams = {(a, b) for a, b in zip(chord_labels, chord_labels[1:]) if a and b}
    features["progression_bigram_count"] = len(bigrams)

    # ── Cadences ──
    all_cadences = cadences + phrase_endings
    features["cadence_count"] = len(all_cadences)
    cad_types = Counter(c.get("cadence_type", c.get("type", "")) for c in all_cadences)
    features["cadence_PAC"] = cad_types.get("PAC", 0)
    features["cadence_IAC"] = cad_types.get("IAC", 0)
    features["cadence_HC"] = cad_types.get("HC", 0)
    features["cadence_DC"] = cad_types.get("DC", 0)

    # ── Voice leading ──
    features["parallel_5ths"] = counterpoint.get("parallel_5ths", 0)
    features["parallel_8ves"] = counterpoint.get("parallel_8ves", 0)
    features["suspension_count"] = counterpoint.get("suspensions", 0)
    issues = counterpoint.get("issues", [])
    features["voice_crossings"] = sum(1 for i in issues if i.get("type") == "voice_crossing")
    features["contrary_motion"] = vl.get("contrary", 0)
    features["similar_motion"] = vl.get("similar", 0)
    features["oblique_motion"] = vl.get("oblique", 0)
    features["parallel_motion"] = vl.get("parallel", 0)
    features["spacing_violations"] = len(vl.get("spacing_issues", []))
    features["range_violations"] = len(vl.get("range_issues", []))

    # ── Graph-dependent features ──
    if graph is not None:
        pitched = [n for n in graph.notes if n.midi is not None and not n.is_rest]
        features["note_count"] = len(pitched)
        features["total_duration_quarters"] = graph.total_duration()

        # Per-voice melodic features
        by_voice = graph.notes_by_voice()
        for role in ("soprano", "alto", "tenor", "bass"):
            voice_id = _resolve_voice_id(by_voice, role)
            vnotes = [n for n in by_voice.get(voice_id or "", []) if n.midi is not None and not n.is_rest]
            midis = [n.midi for n in vnotes]
            features[f"stepwise_{role}"] = round(_stepwise_fraction(midis), 4)
            if role in ("soprano", "bass"):
                features[f"leap_{role}"] = round(_leap_fraction(midis), 4)
            features[f"range_{role}"] = (max(midis) - min(midis)) if midis else 0

        # Onset / rhythmic
        onsets = sorted({n.offset_quarters for n in pitched})
        features["onset_count"] = len(onsets)
        measure_count = features.get("measure_count", 1) or 1
        features["onset_density_mean"] = round(len(onsets) / measure_count, 2)
        features["harmonic_rhythm_mean"] = round(total_chords / measure_count, 2)

        # Pitch class histogram
        pc_hist = [0] * 12
        for n in pitched:
            pc_hist[n.midi % 12] += 1
        for i in range(12):
            features[f"pitch_class_{i}"] = pc_hist[i]
        features["pitch_class_entropy"] = round(_entropy(pc_hist), 4)
    else:
        # Fill from distributions if available
        features["note_count"] = 0
        features["total_duration_quarters"] = 0
        features["onset_count"] = 0
        features["onset_density_mean"] = 0
        features["harmonic_rhythm_mean"] = 0
        features["pitch_class_entropy"] = 0
        for role in ("soprano", "alto", "tenor", "bass"):
            features[f"stepwise_{role}"] = 0
            if role in ("soprano", "bass"):
                features[f"leap_{role}"] = 0
            features[f"range_{role}"] = 0
        pc_hist_data = distributions.get("pitch_class_histogram", {})
        for i in range(12):
            features[f"pitch_class_{i}"] = pc_hist_data.get(str(i), 0)

    return features


def extract_note_sequences(graph: EventGraph) -> dict[str, list]:
    """Extract raw note-level sequences per voice for ML consumption."""
    by_voice = graph.notes_by_voice()
    sequences: dict[str, list] = {}
    for role in ("soprano", "alto", "tenor", "bass"):
        voice_id = _resolve_voice_id(by_voice, role)
        vnotes = sorted(
            [n for n in by_voice.get(voice_id or "", []) if n.midi is not None and not n.is_rest],
            key=lambda n: n.offset_quarters,
        )
        sequences[f"pitch_{role}"] = [n.midi for n in vnotes]
        sequences[f"duration_{role}"] = [n.duration_quarters for n in vnotes]
        sequences[f"onset_{role}"] = [n.offset_quarters for n in vnotes]
    return sequences


# ── Export functions ──────────────────────────────────────────────────────


def export_dataset_csv(rows: list[dict], output: Path) -> None:
    """Write feature rows to CSV."""
    if not rows:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_dataset_json(rows: list[dict], output: Path) -> None:
    """Write feature rows to JSON."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def export_dataset_huggingface(rows: list[dict], note_sequences: list[dict], output: Path) -> None:
    """Export to HuggingFace Dataset format (requires `datasets` package)."""
    try:
        from datasets import Dataset
    except ImportError:
        raise ImportError("HuggingFace export requires: pip install datasets")

    # Merge features with note sequences
    combined = []
    for feat, seq in zip(rows, note_sequences):
        combined.append({**feat, **seq})

    ds = Dataset.from_list(combined)
    output.parent.mkdir(parents=True, exist_ok=True)
    ds.save_to_disk(str(output))
