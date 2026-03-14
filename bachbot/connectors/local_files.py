"""Local file discovery utilities."""

from __future__ import annotations

from pathlib import Path


class LocalFilesConnector:
    def discover(self, root: str | Path) -> list[Path]:
        base = Path(root)
        if not base.exists():
            return []
        return sorted(
            [
                path
                for path in base.rglob("*")
                if path.is_file() and path.suffix.lower() in {".musicxml", ".xml", ".mei", ".krn", ".mscx", ".tsv"}
            ]
        )


def discover_symbolic_files(root: str | Path) -> list[Path]:
    return LocalFilesConnector().discover(root)


def load_symbolic_file(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
