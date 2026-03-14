"""Modulation graph: key regions and modulation edges from harmonic analysis.

Segments harmony events into contiguous key regions via the ``local_key`` field,
classifies modulation types at boundaries (common-chord/pivot, chromatic, direct),
and computes tonal distance via circle-of-fifths.
"""

from __future__ import annotations

from pydantic import Field

from bachbot.analysis.harmony.cadence import summarize_harmony
from bachbot.analysis.harmony.roman_candidates import (
    MAJOR,
    MINOR,
    NOTE_TO_PC,
    _DEGREE_ROOTS_MAJOR,
    _DEGREE_ROOTS_MINOR,
)
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import BachbotModel
from bachbot.models.harmonic_event import HarmonicEvent


# ── Models ──


class KeyRegion(BachbotModel):
    """A contiguous span of music in a single key."""

    region_id: str
    key: str  # e.g., "C major"
    tonic: str
    mode: str
    measure_start: int
    measure_end: int
    onset_start: float
    onset_end: float
    event_count: int


class ModulationEdge(BachbotModel):
    """A transition between two key regions."""

    edge_id: str
    from_region: str
    to_region: str
    from_key: str
    to_key: str
    modulation_type: str  # "common_chord", "chromatic", "direct"
    pivot_chord: str | None = None
    measure: int
    tonal_distance: int


class ModulationGraph(BachbotModel):
    """Directed graph of key regions and modulation edges."""

    encoding_id: str
    global_key: str
    regions: list[KeyRegion] = Field(default_factory=list)
    edges: list[ModulationEdge] = Field(default_factory=list)
    tonal_plan: str = ""


# ── Circle-of-fifths distance ──

# Position on circle of fifths: C=0, G=1, D=2, ..., F=11
_FIFTHS_POS = {pc: (pc * 7) % 12 for pc in range(12)}


def tonal_distance(key_a: str, key_b: str) -> int:
    """Compute circle-of-fifths distance between two keys.

    Relative major/minor pairs (e.g., C major / A minor) have distance 0.
    Returns minimum steps around the circle (0–6).
    """
    parts_a = key_a.split()
    parts_b = key_b.split()
    tonic_a = NOTE_TO_PC.get(parts_a[0], 0)
    tonic_b = NOTE_TO_PC.get(parts_b[0], 0)
    mode_a = parts_a[1] if len(parts_a) > 1 else "major"
    mode_b = parts_b[1] if len(parts_b) > 1 else "major"

    # Normalize to major equivalent for relative-key comparison
    # A minor → C major (add 3 semitones)
    major_pc_a = tonic_a if mode_a == "major" else (tonic_a + 3) % 12
    major_pc_b = tonic_b if mode_b == "major" else (tonic_b + 3) % 12

    pos_a = _FIFTHS_POS[major_pc_a]
    pos_b = _FIFTHS_POS[major_pc_b]
    raw = abs(pos_a - pos_b)
    return min(raw, 12 - raw)


# ── Modulation type classification ──


def _chord_abs_pcs(label: str, key: str) -> set[int] | None:
    """Return the absolute pitch-class set for a Roman numeral in the given key.

    Returns None for secondary dominants or unrecognized labels.
    """
    if "/" in label:
        return None
    parts = key.split()
    tonic_pc = NOTE_TO_PC.get(parts[0], 0)
    mode = parts[1] if len(parts) > 1 else "major"
    families = MAJOR if mode == "major" else MINOR
    rel_pcs = families.get(label)
    if rel_pcs is None:
        return None
    return {(tonic_pc + pc) % 12 for pc in rel_pcs}


def _pcs_is_diatonic_in(abs_pcs: set[int], key: str) -> str | None:
    """Check if a set of absolute PCs matches any diatonic chord in the key.

    Returns the matching Roman numeral label, or None.
    """
    parts = key.split()
    tonic_pc = NOTE_TO_PC.get(parts[0], 0)
    mode = parts[1] if len(parts) > 1 else "major"
    families = MAJOR if mode == "major" else MINOR
    for label, rel_pcs in families.items():
        chord_abs = {(tonic_pc + pc) % 12 for pc in rel_pcs}
        if chord_abs == abs_pcs:
            return label
    return None


def _classify_modulation(
    exit_event: HarmonicEvent,
    entry_event: HarmonicEvent,
    from_key: str,
    to_key: str,
) -> tuple[str, str | None]:
    """Classify modulation type and identify pivot chord if applicable.

    Returns (modulation_type, pivot_chord_label).

    A chord is a **common chord** (pivot) only when its absolute pitch classes
    form a valid diatonic triad in *both* keys.  Secondary-dominant labels are
    always classified as **chromatic**.
    """
    exit_label = exit_event.roman_numeral_candidate_set[0] if exit_event.roman_numeral_candidate_set else None
    entry_label = entry_event.roman_numeral_candidate_set[0] if entry_event.roman_numeral_candidate_set else None

    # Secondary dominant at boundary → chromatic
    if exit_label and "/" in exit_label:
        return "chromatic", None
    if entry_label and "/" in entry_label:
        return "chromatic", None

    # Check exit chord: compute its absolute PCs in from_key, see if it also
    # matches a diatonic chord in to_key
    if exit_label:
        exit_pcs = _chord_abs_pcs(exit_label, from_key)
        if exit_pcs is not None:
            match_in_to = _pcs_is_diatonic_in(exit_pcs, to_key)
            if match_in_to is not None:
                return "common_chord", exit_label

    # Check entry chord: compute its absolute PCs in to_key, see if it also
    # matches a diatonic chord in from_key
    if entry_label:
        entry_pcs = _chord_abs_pcs(entry_label, to_key)
        if entry_pcs is not None:
            match_in_from = _pcs_is_diatonic_in(entry_pcs, from_key)
            if match_in_from is not None:
                return "common_chord", entry_label

    return "direct", None


# ── Region segmentation ──

_MIN_REGION_EVENTS = 3  # Minimum events to form a standalone region


def _segment_regions(
    events: list[HarmonicEvent],
    encoding_id: str,
    global_key: str,
) -> list[tuple[KeyRegion, list[HarmonicEvent]]]:
    """Group consecutive events by local_key into KeyRegions.

    Short regions (< _MIN_REGION_EVENTS events) are merged into the
    preceding region to filter noise from windowed key estimation.
    """
    if not events:
        return []

    # Phase 1: Raw grouping by local_key
    raw_groups: list[tuple[str, list[HarmonicEvent]]] = []
    for event in events:
        key = event.local_key or global_key
        if raw_groups and raw_groups[-1][0] == key:
            raw_groups[-1][1].append(event)
        else:
            raw_groups.append((key, [event]))

    # Phase 2: Merge short groups into predecessor
    merged: list[tuple[str, list[HarmonicEvent]]] = []
    for key, group_events in raw_groups:
        if len(group_events) < _MIN_REGION_EVENTS and merged:
            merged[-1][1].extend(group_events)
        else:
            merged.append((key, group_events))

    # Phase 3: Re-merge any resulting consecutive same-key groups
    final: list[tuple[str, list[HarmonicEvent]]] = []
    for key, group_events in merged:
        if final and final[-1][0] == key:
            final[-1][1].extend(group_events)
        else:
            final.append((key, group_events))

    # Build KeyRegion objects
    results: list[tuple[KeyRegion, list[HarmonicEvent]]] = []
    for i, (key, group_events) in enumerate(final):
        parts = key.split()
        tonic = parts[0] if parts else "C"
        mode = parts[1] if len(parts) > 1 else "major"
        measures = [_event_measure(e) for e in group_events]
        region = KeyRegion(
            region_id=f"{encoding_id}:kr:{i}",
            key=key,
            tonic=tonic,
            mode=mode,
            measure_start=min(measures),
            measure_end=max(measures),
            onset_start=group_events[0].onset,
            onset_end=group_events[-1].onset + group_events[-1].duration,
            event_count=len(group_events),
        )
        results.append((region, group_events))

    return results


def _event_measure(event: HarmonicEvent) -> int:
    """Extract measure number from the event's ref_id."""
    # ref_id format: "<encoding_id>:m<measure_number>"
    parts = event.ref_id.rsplit("m", 1)
    if len(parts) == 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 1


# ── Tonal plan summarization ──

_DEGREE_LABELS_MAJOR = {v: k for k, v in _DEGREE_ROOTS_MAJOR.items()}
_DEGREE_LABELS_MINOR = {v: k for k, v in _DEGREE_ROOTS_MINOR.items()}


def _key_as_degree(region_key: str, global_key: str) -> str:
    """Express a key region as a scale degree relative to the global key.

    E.g., G major relative to C major → "V", A minor relative to C major → "vi".
    """
    g_parts = global_key.split()
    r_parts = region_key.split()
    g_tonic = NOTE_TO_PC.get(g_parts[0], 0)
    r_tonic = NOTE_TO_PC.get(r_parts[0], 0)
    g_mode = g_parts[1] if len(g_parts) > 1 else "major"
    r_mode = r_parts[1] if len(r_parts) > 1 else "major"
    interval = (r_tonic - g_tonic) % 12

    degree_map = _DEGREE_LABELS_MAJOR if g_mode == "major" else _DEGREE_LABELS_MINOR
    label = degree_map.get(interval)
    if label:
        return label

    # Fallback: use the interval as a chromatic step
    return f"[{interval}]"


def _summarize_tonal_plan(regions: list[KeyRegion], global_key: str) -> str:
    """Produce a tonal plan string like 'I–V–I' or 'i–III–v–i'."""
    if not regions:
        return ""
    degrees = [_key_as_degree(r.key, global_key) for r in regions]
    # Deduplicate consecutive identical degrees
    deduped = [degrees[0]]
    for d in degrees[1:]:
        if d != deduped[-1]:
            deduped.append(d)
    return "–".join(deduped)


# ── Public API ──


def build_modulation_graph(graph: EventGraph) -> ModulationGraph:
    """Build a modulation graph from an EventGraph.

    Segments harmony events into key regions, classifies modulation types
    at boundaries, and computes circle-of-fifths tonal distances.
    """
    key = graph.metadata.key_estimate
    if key is None:
        raise ValueError("Key estimate required")

    global_key = f"{key.tonic} {key.mode}"
    events = summarize_harmony(graph)
    encoding_id = graph.metadata.encoding_id

    region_pairs = _segment_regions(events, encoding_id, global_key)
    regions = [r for r, _ in region_pairs]

    edges: list[ModulationEdge] = []
    for i in range(len(region_pairs) - 1):
        from_region, from_events = region_pairs[i]
        to_region, to_events = region_pairs[i + 1]

        if from_region.key == to_region.key:
            continue  # No modulation

        mod_type, pivot = _classify_modulation(
            from_events[-1], to_events[0], from_region.key, to_region.key,
        )
        dist = tonal_distance(from_region.key, to_region.key)
        edges.append(
            ModulationEdge(
                edge_id=f"{encoding_id}:mod:{i}",
                from_region=from_region.region_id,
                to_region=to_region.region_id,
                from_key=from_region.key,
                to_key=to_region.key,
                modulation_type=mod_type,
                pivot_chord=pivot,
                measure=to_region.measure_start,
                tonal_distance=dist,
            )
        )

    tonal_plan = _summarize_tonal_plan(regions, global_key)

    return ModulationGraph(
        encoding_id=encoding_id,
        global_key=global_key,
        regions=regions,
        edges=edges,
        tonal_plan=tonal_plan,
    )


def build_modulation_graph_from_events(
    events: list[HarmonicEvent],
    encoding_id: str,
    global_key: str,
) -> ModulationGraph:
    """Build a modulation graph from pre-computed harmonic events.

    Useful when harmony has already been summarized (e.g., from an evidence bundle).
    """
    region_pairs = _segment_regions(events, encoding_id, global_key)
    regions = [r for r, _ in region_pairs]

    edges: list[ModulationEdge] = []
    for i in range(len(region_pairs) - 1):
        from_region, from_events = region_pairs[i]
        to_region, to_events = region_pairs[i + 1]

        if from_region.key == to_region.key:
            continue

        mod_type, pivot = _classify_modulation(
            from_events[-1], to_events[0], from_region.key, to_region.key,
        )
        dist = tonal_distance(from_region.key, to_region.key)
        edges.append(
            ModulationEdge(
                edge_id=f"{encoding_id}:mod:{i}",
                from_region=from_region.region_id,
                to_region=to_region.region_id,
                from_key=from_region.key,
                to_key=to_region.key,
                modulation_type=mod_type,
                pivot_chord=pivot,
                measure=to_region.measure_start,
                tonal_distance=dist,
            )
        )

    tonal_plan = _summarize_tonal_plan(regions, global_key)

    return ModulationGraph(
        encoding_id=encoding_id,
        global_key=global_key,
        regions=regions,
        edges=edges,
        tonal_plan=tonal_plan,
    )
