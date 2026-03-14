"""System adapters for cross-system composition benchmarking."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from bachbot.benchmark.cross_system.test_set import BenchmarkMelody
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.models.base import TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice

# ── Corpus paths for ground truth loading ────────────────────────────

_CORPUS_NORM = Path("data/normalized/dcml_bach_chorales")


# ── Helper: build soprano-only EventGraph from BenchmarkMelody ────────────

def _melody_to_cantus(melody: BenchmarkMelody) -> EventGraph:
    """Convert a BenchmarkMelody into a soprano-only EventGraph suitable for composition."""
    wid = melody.melody_id
    sid = f"{wid}:section:1"
    bpn = melody.beats_per_note

    notes: list[TypedNote] = []
    offset = 0.0
    measure = 1
    # Parse meter for beats per measure
    try:
        num, den = melody.meter.split("/")
        beats_per_measure = int(num) * (4.0 / int(den))
    except Exception:
        beats_per_measure = 4.0

    for midi in melody.soprano_midi:
        beat_in_measure = (offset % beats_per_measure) + 1
        notes.append(TypedNote(
            pitch=None,
            midi=midi,
            duration_quarters=bpn,
            offset_quarters=offset,
            measure_number=measure,
            beat=beat_in_measure,
            voice_id="Soprano:1",
        ))
        offset += bpn
        if offset >= measure * beats_per_measure:
            measure += 1

    m_end = notes[-1].measure_number if notes else 1

    key_est = None
    if melody.key:
        from bachbot.models.base import KeyEstimate
        key_est = KeyEstimate(tonic=melody.key, mode=melody.mode, confidence=0.99)

    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id=wid,
            work_id=wid,
            source_format="cross-system-benchmark",
            meter=melody.meter,
            key_estimate=key_est,
        ),
        section=Section(
            section_id=sid,
            work_id=wid,
            label="Cross-system benchmark cantus",
            section_type="cantus",
            measure_start=1,
            measure_end=m_end,
        ),
        voices=[Voice(
            voice_id="Soprano:1",
            section_id=sid,
            part_name="Soprano",
            normalized_voice_name="Soprano",
        )],
        notes=notes,
    )


def _load_evidence_bundle(work_id: str) -> dict | None:
    """Try to load an evidence bundle for a work_id from the derived corpus."""
    derived = Path("data/derived/dcml_bach_chorales")
    # Work IDs in corpus look like "notes__001 Aus meines Herzens Grunde"
    for bp in derived.glob("*.evidence_bundle.json"):
        stem = bp.name.replace(".evidence_bundle.json", "")
        if stem == work_id:
            try:
                return json.loads(bp.read_text(encoding="utf-8"))
            except Exception:
                return None
    return None


# ── Abstract base ────────────────────────────────────────────────────

class SystemAdapter(ABC):
    """Abstract adapter for a harmonization system."""

    name: str = ""

    @abstractmethod
    def harmonize(self, melody: BenchmarkMelody) -> EventGraph | None:
        """Harmonize a melody and return an EventGraph, or None on failure."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this system is installed/accessible."""


# ── Bachbot adapter ──────────────────────────────────────────────────

class BachbotAdapter(SystemAdapter):
    """Uses Bachbot's own composition engine."""

    name = "bachbot"

    def is_available(self) -> bool:
        return True

    def harmonize(self, melody: BenchmarkMelody) -> EventGraph | None:
        from bachbot.composition.service import compose_chorale_study

        cantus = _melody_to_cantus(melody)
        bundle = None
        if melody.ground_truth_work_id:
            bundle = _load_evidence_bundle(melody.ground_truth_work_id)
        try:
            graph, _, _ = compose_chorale_study(cantus, bundle=bundle)
            return graph
        except Exception:
            return None


# ── Ground truth adapter ─────────────────────────────────────────────

class GroundTruthAdapter(SystemAdapter):
    """Returns Bach's original harmonization from the corpus."""

    name = "ground_truth"

    def is_available(self) -> bool:
        return _CORPUS_NORM.exists() and any(_CORPUS_NORM.glob("*.event_graph.json"))

    def harmonize(self, melody: BenchmarkMelody) -> EventGraph | None:
        if not melody.ground_truth_work_id:
            return None
        wid = melody.ground_truth_work_id
        for gp in _CORPUS_NORM.glob("*.event_graph.json"):
            stem = gp.name.replace(".event_graph.json", "")
            if stem == wid:
                try:
                    return EventGraph.model_validate(json.loads(gp.read_text(encoding="utf-8")))
                except Exception:
                    return None
        return None


# ── Music21 adapter ──────────────────────────────────────────────────

class Music21Adapter(SystemAdapter):
    """Imports music21 harmonizations via figured bass realization."""

    name = "music21"

    def is_available(self) -> bool:
        try:
            import music21  # noqa: F401
            return True
        except ImportError:
            return False

    def harmonize(self, melody: BenchmarkMelody) -> EventGraph | None:
        try:
            import music21 as m21
        except ImportError:
            return None

        try:
            s = m21.stream.Score()
            part = m21.stream.Part()
            for midi_val in melody.soprano_midi:
                n = m21.note.Note(midi=midi_val, quarterLength=melody.beats_per_note)
                part.append(n)
            s.insert(0, part)

            # Use music21's chord realization as a simple harmonization proxy.
            # This is a minimal integration — music21 doesn't have a direct
            # 4-part harmonizer, so we use chordify as an approximation.
            chordified = s.chordify()
            return EventGraph.from_music21(chordified, work_id=f"music21:{melody.melody_id}")
        except Exception:
            return None


# ── MIDI import adapter ──────────────────────────────────────────────

class MidiImportAdapter(SystemAdapter):
    """Imports pre-generated MIDI harmonizations for external systems (DeepBach, Coconet, etc.)."""

    name = "midi_import"

    def __init__(self, midi_dir: Path | str = Path("data/cross_system_midi")):
        self._midi_dir = Path(midi_dir)

    def is_available(self) -> bool:
        return self._midi_dir.exists()

    def harmonize(self, melody: BenchmarkMelody) -> EventGraph | None:
        # Look for a MIDI file matching the melody_id
        safe_id = melody.melody_id.replace(":", "_").replace("/", "_")
        candidates = [
            self._midi_dir / f"{safe_id}.mid",
            self._midi_dir / f"{safe_id}.midi",
            self._midi_dir / f"{melody.melody_id}.mid",
        ]
        midi_path = None
        for c in candidates:
            if c.exists():
                midi_path = c
                break
        if midi_path is None:
            return None

        try:
            import music21 as m21
            score = m21.converter.parse(str(midi_path))
            return EventGraph.from_music21(score, work_id=f"midi_import:{melody.melody_id}")
        except Exception:
            return None


# ── Adapter registry ─────────────────────────────────────────────────

ADAPTER_REGISTRY: dict[str, type[SystemAdapter]] = {
    "bachbot": BachbotAdapter,
    "ground_truth": GroundTruthAdapter,
    "music21": Music21Adapter,
    "midi_import": MidiImportAdapter,
}


def get_adapter(name: str) -> SystemAdapter:
    """Instantiate an adapter by name."""
    cls = ADAPTER_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown adapter: {name!r}. Available: {sorted(ADAPTER_REGISTRY)}")
    return cls()
