"""SVG generation helpers for Jupyter visualization."""

from __future__ import annotations

from xml.sax.saxutils import escape


# Voice colors: Soprano=blue, Alto=green, Tenor=orange, Bass=red
_VOICE_COLORS: dict[str, str] = {
    "Soprano:1": "#4477AA",
    "Alto:1": "#44AA77",
    "Tenor:1": "#DDAA33",
    "Bass:1": "#CC4444",
    "S": "#4477AA",
    "A": "#44AA77",
    "T": "#DDAA33",
    "B": "#CC4444",
}

_FALLBACK_COLORS = ["#4477AA", "#44AA77", "#DDAA33", "#CC4444", "#8866CC", "#CC6688"]


def voice_color(voice_id: str) -> str:
    """Return a consistent color for a given voice_id."""
    if voice_id in _VOICE_COLORS:
        return _VOICE_COLORS[voice_id]
    lowered = voice_id.lower()
    if "soprano" in lowered or lowered.startswith("s"):
        return "#4477AA"
    if "alto" in lowered or lowered.startswith("a"):
        return "#44AA77"
    if "tenor" in lowered or lowered.startswith("t"):
        return "#DDAA33"
    if "bass" in lowered or lowered.startswith("b"):
        return "#CC4444"
    # Deterministic fallback based on hash
    return _FALLBACK_COLORS[hash(voice_id) % len(_FALLBACK_COLORS)]


def midi_to_y(midi: int, y_min: float, y_max: float, midi_low: int, midi_high: int) -> float:
    """Map MIDI pitch to Y coordinate (higher pitch = lower Y for visual clarity)."""
    if midi_high == midi_low:
        return (y_min + y_max) / 2
    return y_max - (midi - midi_low) / (midi_high - midi_low) * (y_max - y_min)


def onset_to_x(onset: float, x_min: float, x_max: float, total_duration: float) -> float:
    """Map onset time to X coordinate."""
    if total_duration <= 0:
        return x_min
    return x_min + (onset / total_duration) * (x_max - x_min)


class SVGCanvas:
    """Lightweight SVG builder producing valid XML strings."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.elements: list[str] = []

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str,
        *,
        title: str | None = None,
        opacity: float = 1.0,
        stroke: str | None = None,
        stroke_width: float = 0,
        rx: float = 0,
    ) -> None:
        attrs = (
            f'x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{fill}" opacity="{opacity}"'
        )
        if stroke:
            attrs += f' stroke="{stroke}" stroke-width="{stroke_width}"'
        if rx > 0:
            attrs += f' rx="{rx}"'
        if title:
            self.elements.append(f"<rect {attrs}><title>{escape(title)}</title></rect>")
        else:
            self.elements.append(f"<rect {attrs}/>")

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke: str,
        *,
        width: float = 1,
        dash: str | None = None,
        opacity: float = 1.0,
    ) -> None:
        attrs = (
            f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"'
        )
        if dash:
            attrs += f' stroke-dasharray="{dash}"'
        self.elements.append(f"<line {attrs}/>")

    def text(
        self,
        x: float,
        y: float,
        content: str,
        *,
        font_size: int = 10,
        fill: str = "black",
        anchor: str = "start",
        font_weight: str = "normal",
        font_family: str = "sans-serif",
    ) -> None:
        self.elements.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{font_size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{font_weight}" '
            f'font-family="{font_family}">{escape(content)}</text>'
        )

    def group(self, elements: list[str], *, transform: str | None = None) -> None:
        attrs = f' transform="{transform}"' if transform else ""
        self.elements.append(f"<g{attrs}>")
        self.elements.extend(elements)
        self.elements.append("</g>")

    def render(self) -> str:
        """Return complete SVG XML string."""
        body = "\n".join(self.elements)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}" '
            f'style="background:#fafafa;font-family:sans-serif">\n'
            f"{body}\n</svg>"
        )
