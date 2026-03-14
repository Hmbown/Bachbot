"""Display functions for Jupyter notebook visualization of Bachbot objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bachbot.analysis.pipeline import AnalysisReport
from bachbot.claims.bundle import EvidenceBundle
from bachbot.encodings.event_graph import EventGraph
from bachbot.jupyter.piano_roll import render_piano_roll
from bachbot.jupyter.svg import SVGCanvas, midi_to_y, onset_to_x, voice_color

if TYPE_CHECKING:
    pass


def _get_html_class():
    """Import IPython.display.HTML with a helpful error if not available."""
    try:
        from IPython.display import HTML  # type: ignore[import-not-found]

        return HTML
    except ImportError:
        raise ImportError(
            "IPython is required for Jupyter display. "
            "Install it with: pip install 'bachbot[jupyter]'"
        ) from None


def display_graph(graph: EventGraph, *, width: int = 800, height: int = 400) -> Any:
    """Render EventGraph as inline SVG piano-roll view.

    Returns an IPython.display.HTML object suitable for Jupyter display.
    """
    HTML = _get_html_class()
    svg = render_piano_roll(graph, width=width, height=height)
    return HTML(svg)


def display_analysis(
    graph: EventGraph,
    analysis: AnalysisReport,
    *,
    width: int = 800,
    height: int = 500,
) -> Any:
    """Render piano roll with harmonic analysis overlay.

    Top: piano roll. Bottom: roman numerals, cadence markers, key regions.
    Returns an IPython.display.HTML object.
    """
    HTML = _get_html_class()
    svg = render_analysis_svg(graph, analysis, width=width, height=height)
    return HTML(svg)


def display_bundle(bundle: EvidenceBundle, *, width: int = 800, height: int = 500) -> Any:
    """Render analysis view from an EvidenceBundle.

    Extracts harmony, cadences, and modulation data from deterministic_findings.
    Returns an IPython.display.HTML object.
    """
    HTML = _get_html_class()
    svg = render_bundle_svg(bundle, width=width, height=height)
    return HTML(svg)


def display_voice_leading(graph: EventGraph, *, width: int = 800, height: int = 300) -> Any:
    """Draw voice-leading connections as lines between adjacent beats.

    Color by interval quality: stepwise=green, leap=orange, parallel 5th/8ve=red.
    Returns an IPython.display.HTML object.
    """
    HTML = _get_html_class()
    svg = render_voice_leading_svg(graph, width=width, height=height)
    return HTML(svg)


# ---------------------------------------------------------------------------
# SVG renderers (return raw SVG strings, no IPython dependency)
# ---------------------------------------------------------------------------

_MARGIN_LEFT = 50
_MARGIN_RIGHT = 20
_MARGIN_TOP = 30
_MARGIN_BOTTOM = 80
_ANALYSIS_HEIGHT = 60


def render_analysis_svg(
    graph: EventGraph,
    analysis: AnalysisReport,
    *,
    width: int = 800,
    height: int = 500,
) -> str:
    """Render piano roll + harmonic analysis as SVG string."""
    canvas = SVGCanvas(width, height)
    pitch_events = graph.pitch_events()
    total_duration = graph.total_duration() or 1.0

    x_min = _MARGIN_LEFT
    x_max = width - _MARGIN_RIGHT
    piano_y_min = _MARGIN_TOP
    piano_y_max = height - _MARGIN_BOTTOM - _ANALYSIS_HEIGHT
    analysis_y_top = piano_y_max + 10
    analysis_y_bot = height - _MARGIN_BOTTOM + 20

    if not pitch_events:
        canvas.text(width / 2, height / 2, "No pitch events", font_size=14, anchor="middle")
        return canvas.render()

    midi_values = [n.midi for n in pitch_events if n.midi is not None]
    midi_low = min(midi_values) - 2
    midi_high = max(midi_values) + 2

    # Piano roll background
    canvas.rect(x_min, piano_y_min, x_max - x_min, piano_y_max - piano_y_min, "#f0f0f0")

    # Measure lines
    measure_numbers = graph.measure_numbers()
    notes_by_measure = graph.notes_by_measure()
    for m_num in measure_numbers:
        m_notes = notes_by_measure.get(m_num, [])
        if m_notes:
            m_onset = min(n.offset_quarters for n in m_notes)
            mx = onset_to_x(m_onset, x_min, x_max, total_duration)
            canvas.line(mx, piano_y_min, mx, analysis_y_bot, "#cccccc", width=0.5)
            canvas.text(mx + 2, piano_y_min - 4, str(m_num), font_size=8, fill="#888888")

    # Note rectangles
    pitch_range = midi_high - midi_low
    note_h = max(4, min(12, (piano_y_max - piano_y_min) / max(pitch_range, 1) * 0.8))
    for vid, notes in graph.notes_by_voice().items():
        color = voice_color(vid)
        for note in notes:
            if note.is_rest or note.midi is None:
                continue
            nx = onset_to_x(note.offset_quarters, x_min, x_max, total_duration)
            nw = max(2.0, (note.duration_quarters / total_duration) * (x_max - x_min))
            ny = midi_to_y(note.midi, piano_y_min, piano_y_max, midi_low, midi_high) - note_h / 2
            canvas.rect(nx, ny, nw, note_h, color, opacity=0.85, rx=1)

    # Harmonic analysis: roman numerals
    _render_harmony_overlay(canvas, analysis, x_min, x_max, analysis_y_top, analysis_y_bot, total_duration)

    # Cadence markers
    _render_cadence_markers(canvas, analysis, x_min, x_max, piano_y_min, analysis_y_bot, total_duration)

    # Key region backgrounds
    _render_key_regions(canvas, analysis, x_min, x_max, analysis_y_top, analysis_y_bot, total_duration)

    # Title
    title_text = graph.title or "Analysis"
    canvas.text(width / 2, 16, title_text, font_size=12, anchor="middle", font_weight="bold")

    return canvas.render()


def _render_harmony_overlay(
    canvas: SVGCanvas,
    analysis: AnalysisReport,
    x_min: float,
    x_max: float,
    y_top: float,
    y_bot: float,
    total_duration: float,
) -> None:
    """Add roman numeral labels below the piano roll."""
    label_y = y_top + (y_bot - y_top) / 2 + 4
    for event in analysis.harmony:
        ex = onset_to_x(event.onset, x_min, x_max, total_duration)
        label = event.roman_numeral_candidate_set[0] if event.roman_numeral_candidate_set else "?"
        canvas.text(ex, label_y, label, font_size=9, fill="#333333", anchor="start")
        if event.local_key:
            canvas.text(ex, label_y + 11, event.local_key, font_size=7, fill="#888888", anchor="start")


def _render_cadence_markers(
    canvas: SVGCanvas,
    analysis: AnalysisReport,
    x_min: float,
    x_max: float,
    y_top: float,
    y_bot: float,
    total_duration: float,
) -> None:
    """Draw vertical cadence markers."""
    for cadence in analysis.cadences:
        # Extract onset from ref_id (format: HE-<id>-<onset>)
        parts = cadence.ref_id.split("-")
        try:
            onset = float(parts[-1]) if len(parts) >= 3 else 0.0
        except (ValueError, IndexError):
            continue
        cx = onset_to_x(onset, x_min, x_max, total_duration)
        canvas.line(cx, y_top, cx, y_bot, "#CC0000", width=1.5, dash="4,2")
        label = cadence.cadence_type[:3].upper() if cadence.cadence_type else "CAD"
        canvas.text(cx + 2, y_top - 2, label, font_size=7, fill="#CC0000", font_weight="bold")


def _render_key_regions(
    canvas: SVGCanvas,
    analysis: AnalysisReport,
    x_min: float,
    x_max: float,
    y_top: float,
    y_bot: float,
    total_duration: float,
) -> None:
    """Color-code key regions from the modulation graph if present."""
    mod_graph = analysis.modulation_graph
    if not mod_graph or "regions" not in mod_graph:
        return
    key_colors = ["#E8F0FE", "#FEF3E8", "#E8FEF0", "#FEE8F0", "#F0E8FE", "#FEF8E8"]
    for i, region in enumerate(mod_graph["regions"]):
        r_onset = region.get("onset_start", 0.0)
        r_end = region.get("onset_end", total_duration)
        rx = onset_to_x(r_onset, x_min, x_max, total_duration)
        rw = onset_to_x(r_end, x_min, x_max, total_duration) - rx
        color = key_colors[i % len(key_colors)]
        canvas.rect(rx, y_top, max(rw, 1), y_bot - y_top, color, opacity=0.3)


def render_bundle_svg(bundle: EvidenceBundle, *, width: int = 800, height: int = 500) -> str:
    """Render analysis view from an EvidenceBundle (SVG string)."""
    canvas = SVGCanvas(width, height)
    findings = bundle.deterministic_findings

    x_min = _MARGIN_LEFT
    x_max = width - _MARGIN_RIGHT
    y_min = _MARGIN_TOP
    y_max = height - _MARGIN_BOTTOM

    harmony = findings.get("harmony", [])
    cadences = findings.get("cadences", [])

    if not harmony:
        canvas.text(width / 2, height / 2, "No harmonic data in bundle", font_size=14, anchor="middle")
        return canvas.render()

    # Determine total duration from harmony events
    total_duration = max(
        (h.get("onset", 0) + h.get("duration", 0) for h in harmony),
        default=1.0,
    )
    if total_duration <= 0:
        total_duration = 1.0

    # Title
    title = f"Evidence Bundle: {bundle.bundle_id}"
    if bundle.metadata.key:
        title += f" ({bundle.metadata.key})"
    canvas.text(width / 2, 16, title, font_size=12, anchor="middle", font_weight="bold")

    # Background
    canvas.rect(x_min, y_min, x_max - x_min, y_max - y_min, "#f8f8f8")

    # Harmony blocks and labels
    block_y = y_min + 20
    block_h = 30
    label_y = block_y + block_h + 15
    key_y = label_y + 12

    for h_event in harmony:
        onset = h_event.get("onset", 0)
        dur = h_event.get("duration", 0)
        hx = onset_to_x(onset, x_min, x_max, total_duration)
        hw = max(2.0, (dur / total_duration) * (x_max - x_min))
        canvas.rect(hx, block_y, hw, block_h, "#D4E6F1", opacity=0.6, stroke="#AAC4D7", stroke_width=0.5)

        candidates = h_event.get("roman_numeral_candidate_set", [])
        label = candidates[0] if candidates else "?"
        canvas.text(hx + 2, label_y, label, font_size=9, fill="#333333")

        local_key = h_event.get("local_key")
        if local_key:
            canvas.text(hx + 2, key_y, local_key, font_size=7, fill="#888888")

    # Cadence markers
    for cad in cadences:
        ref_id = cad.get("ref_id", "")
        parts = ref_id.split("-")
        try:
            onset = float(parts[-1]) if len(parts) >= 3 else 0.0
        except (ValueError, IndexError):
            continue
        cx = onset_to_x(onset, x_min, x_max, total_duration)
        canvas.line(cx, y_min, cx, y_max, "#CC0000", width=1.5, dash="4,2")
        ctype = cad.get("cadence_type", "cad")[:3].upper()
        canvas.text(cx + 2, y_max + 12, ctype, font_size=7, fill="#CC0000", font_weight="bold")

    # Nonharmonic tone summary
    nht_count = sum(
        len(h.get("nonharmonic_tone_tags", [])) for h in harmony
    )
    canvas.text(
        x_min, y_max + 25,
        f"Harmonic events: {len(harmony)} | Cadences: {len(cadences)} | NHT tags: {nht_count}",
        font_size=9,
        fill="#666666",
    )

    return canvas.render()


def render_voice_leading_svg(graph: EventGraph, *, width: int = 800, height: int = 300) -> str:
    """Render voice-leading connections as SVG string.

    Lines between adjacent beats, colored by interval quality:
    stepwise (1-2 semitones) = green, leap (>2) = orange,
    parallel 5th/8ve = red.
    """
    canvas = SVGCanvas(width, height)
    pitch_events = graph.pitch_events()
    if not pitch_events:
        canvas.text(width / 2, height / 2, "No pitch events", font_size=14, anchor="middle")
        return canvas.render()

    total_duration = graph.total_duration() or 1.0
    midi_values = [n.midi for n in pitch_events if n.midi is not None]
    midi_low = min(midi_values) - 2
    midi_high = max(midi_values) + 2

    x_min = _MARGIN_LEFT
    x_max = width - _MARGIN_RIGHT
    y_min = _MARGIN_TOP
    y_max = height - _MARGIN_BOTTOM

    # Background
    canvas.rect(x_min, y_min, x_max - x_min, y_max - y_min, "#f0f0f0")

    # Title
    canvas.text(width / 2, 16, "Voice Leading", font_size=12, anchor="middle", font_weight="bold")

    # For each voice, draw lines connecting consecutive notes
    for vid in graph.ordered_voice_ids():
        notes = [n for n in graph.voice_events(vid) if n.midi is not None]
        if len(notes) < 2:
            continue
        base_color = voice_color(vid)
        for i in range(len(notes) - 1):
            n1 = notes[i]
            n2 = notes[i + 1]
            if n1.midi is None or n2.midi is None:
                continue
            x1 = onset_to_x(n1.offset_quarters + n1.duration_quarters, x_min, x_max, total_duration)
            y1 = midi_to_y(n1.midi, y_min, y_max, midi_low, midi_high)
            x2 = onset_to_x(n2.offset_quarters, x_min, x_max, total_duration)
            y2 = midi_to_y(n2.midi, y_min, y_max, midi_low, midi_high)

            interval = abs(n2.midi - n1.midi)
            if interval <= 2:
                line_color = "#44AA77"  # stepwise = green
            else:
                line_color = "#DDAA33"  # leap = orange

            canvas.line(x1, y1, x2, y2, line_color, width=1.5, opacity=0.7)

            # Small dots at note positions
            canvas.rect(
                x1 - 2, y1 - 2, 4, 4, base_color,
                title=f"{n1.pitch or ''} -> {n2.pitch or ''} ({interval} st)",
            )

    # Check for parallel 5ths/8ves between outer voices
    _draw_parallel_markers(canvas, graph, x_min, x_max, y_min, y_max, midi_low, midi_high, total_duration)

    return canvas.render()


def _draw_parallel_markers(
    canvas: SVGCanvas,
    graph: EventGraph,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    midi_low: int,
    midi_high: int,
    total_duration: float,
) -> None:
    """Mark parallel 5ths/8ves in red between outer voices."""
    voice_ids = graph.ordered_voice_ids()
    if len(voice_ids) < 2:
        return
    soprano_id = voice_ids[0]
    bass_id = voice_ids[-1]
    soprano_notes = [n for n in graph.voice_events(soprano_id) if n.midi is not None]
    bass_notes = [n for n in graph.voice_events(bass_id) if n.midi is not None]
    if len(soprano_notes) < 2 or len(bass_notes) < 2:
        return

    # Build onset-indexed lookup for bass
    bass_by_onset: dict[float, int] = {}
    for n in bass_notes:
        bass_by_onset[n.offset_quarters] = n.midi  # type: ignore[assignment]

    for i in range(len(soprano_notes) - 1):
        s1, s2 = soprano_notes[i], soprano_notes[i + 1]
        b1_midi = bass_by_onset.get(s1.offset_quarters)
        b2_midi = bass_by_onset.get(s2.offset_quarters)
        if b1_midi is None or b2_midi is None or s1.midi is None or s2.midi is None:
            continue
        int1 = (s1.midi - b1_midi) % 12
        int2 = (s2.midi - b2_midi) % 12
        # Parallel 5th (7 semitones) or 8ve (0 semitones)
        if int1 == int2 and int1 in (0, 7) and s1.midi != s2.midi:
            mx = onset_to_x(
                (s1.offset_quarters + s2.offset_quarters) / 2, x_min, x_max, total_duration
            )
            my = (y_min + y_max) / 2
            label = "P8" if int1 == 0 else "P5"
            canvas.text(mx, my, label, font_size=8, fill="#CC0000", anchor="middle", font_weight="bold")
