"""DCML-like corpus connector for local open symbolic datasets."""

from __future__ import annotations

from pathlib import Path


class DCMLConnector:
    """Discover local files in an open corpus layout."""

    def scan(self, root: str | Path) -> list[Path]:
        corpus_root = Path(root)
        return sorted(
            [
                *corpus_root.rglob("*.musicxml"),
                *corpus_root.rglob("*.xml"),
                *corpus_root.rglob("*.mei"),
                *corpus_root.rglob("*.krn"),
            ]
        )


DCMlConnector = DCMLConnector
