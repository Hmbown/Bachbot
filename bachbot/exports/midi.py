"""MIDI export placeholder."""

from __future__ import annotations

from pathlib import Path


def export_midi_stub(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"MThd")
    return output_path
