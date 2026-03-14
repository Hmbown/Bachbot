from __future__ import annotations

from pathlib import Path

from bachbot.encodings.event_graph import EventGraph
from bachbot.encodings.musicxml_io import parse_musicxml


def normalize_file(path: str | Path, work_id: str | None = None, encoding_id: str | None = None) -> EventGraph:
    path = Path(path)
    suffixes = [suffix.lower() for suffix in path.suffixes]
    if ".musicxml" in suffixes or ".xml" in suffixes:
        return parse_musicxml(path, work_id=work_id, encoding_id=encoding_id)
    if ".notes" in suffixes and ".tsv" in suffixes:
        from bachbot.encodings.dcml_tsv_io import parse_dcml_tsv

        measures_path = path.parent.parent / "measures" / path.name.replace(".notes.tsv", ".measures.tsv")
        return parse_dcml_tsv(path, measures_path=measures_path, work_id=work_id, encoding_id=encoding_id)
    raise ValueError(f"Unsupported encoding type for {path}")

