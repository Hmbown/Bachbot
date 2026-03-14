"""Piano roll renderer for EventGraph visualization."""

from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph
from bachbot.jupyter.svg import SVGCanvas, midi_to_y, onset_to_x, voice_color

# Layout constants
_MARGIN_LEFT = 50
_MARGIN_RIGHT = 20
_MARGIN_TOP = 30
_MARGIN_BOTTOM = 30
_NOTE_HEIGHT_MIN = 4
_NOTE_HEIGHT_MAX = 14


def render_piano_roll(graph: EventGraph, *, width: int = 800, height: int = 400) -> str:
    """Render EventGraph as SVG piano roll.

    X-axis: time (beats/measures). Y-axis: pitch (MIDI).
    Colored rectangles per voice. Measure lines and beat markers.
    Note labels (pitch names) on hover via SVG title elements.
    """
    canvas = SVGCanvas(width, height)
    pitch_events = graph.pitch_events()
    if not pitch_events:
        canvas.text(width / 2, height / 2, "No pitch events", font_size=14, anchor="middle")
        return canvas.render()

    total_duration = graph.total_duration()
    if total_duration <= 0:
        total_duration = 1.0

    midi_values = [n.midi for n in pitch_events if n.midi is not None]
    midi_low = min(midi_values) - 2
    midi_high = max(midi_values) + 2

    x_min = _MARGIN_LEFT
    x_max = width - _MARGIN_RIGHT
    y_min = _MARGIN_TOP
    y_max = height - _MARGIN_BOTTOM

    # Calculate note height based on pitch range
    pitch_range = midi_high - midi_low
    note_h = max(_NOTE_HEIGHT_MIN, min(_NOTE_HEIGHT_MAX, (y_max - y_min) / max(pitch_range, 1) * 0.8))

    # Background
    canvas.rect(x_min, y_min, x_max - x_min, y_max - y_min, "#f0f0f0")

    # Measure lines
    measure_numbers = graph.measure_numbers()
    notes_by_measure = graph.notes_by_measure()
    for m_num in measure_numbers:
        m_notes = notes_by_measure.get(m_num, [])
        if m_notes:
            m_onset = min(n.offset_quarters for n in m_notes)
            mx = onset_to_x(m_onset, x_min, x_max, total_duration)
            canvas.line(mx, y_min, mx, y_max, "#cccccc", width=0.5)
            canvas.text(mx + 2, y_min - 4, str(m_num), font_size=8, fill="#888888")

    # Pitch grid lines (every octave C)
    for midi_val in range(midi_low, midi_high + 1):
        if midi_val % 12 == 0:  # C notes
            gy = midi_to_y(midi_val, y_min, y_max, midi_low, midi_high)
            canvas.line(x_min, gy, x_max, gy, "#dddddd", width=0.5, dash="2,2")
            octave = midi_val // 12 - 1
            canvas.text(x_min - 4, gy + 3, f"C{octave}", font_size=7, fill="#999999", anchor="end")

    # Note rectangles
    voices_by_id = graph.notes_by_voice()
    for vid, notes in voices_by_id.items():
        color = voice_color(vid)
        for note in notes:
            if note.is_rest or note.midi is None:
                continue
            nx = onset_to_x(note.offset_quarters, x_min, x_max, total_duration)
            note_w = max(2.0, (note.duration_quarters / total_duration) * (x_max - x_min))
            ny = midi_to_y(note.midi, y_min, y_max, midi_low, midi_high) - note_h / 2
            title = f"{note.pitch or ''} (MIDI {note.midi}) | {vid} | m.{note.measure_number} beat {note.beat}"
            canvas.rect(nx, ny, note_w, note_h, color, title=title, opacity=0.85, rx=1)

    # Title
    title_text = graph.title or "Piano Roll"
    key_str = ""
    if graph.metadata.key_estimate:
        key_str = f" ({graph.metadata.key_estimate.tonic} {graph.metadata.key_estimate.mode})"
    canvas.text(width / 2, 16, f"{title_text}{key_str}", font_size=12, anchor="middle", font_weight="bold")

    # Legend
    legend_x = x_max - 140
    legend_y = y_max + 12
    for i, vid in enumerate(graph.ordered_voice_ids()):
        lx = legend_x + i * 38
        canvas.rect(lx, legend_y, 10, 10, voice_color(vid))
        canvas.text(lx + 13, legend_y + 9, vid.split(":")[0][:3], font_size=8, fill="#666666")

    return canvas.render()
