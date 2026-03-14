from __future__ import annotations

from pathlib import Path

from bachbot.claims.bundle import EvidenceBundle
from bachbot.claims.reporter import render_markdown_report


def write_markdown_report(bundle: EvidenceBundle, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_report(bundle), encoding="utf-8")
    return path

