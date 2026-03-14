"""SVG/PDF export placeholder."""

from __future__ import annotations

from pathlib import Path


def export_svg_stub(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>\n", encoding="utf-8")
    return output_path
