"""MEI export placeholder."""

from __future__ import annotations

from pathlib import Path


def export_mei(_payload: dict, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("<!-- MEI export planned for a later iteration -->\n", encoding="utf-8")
    return output_path
