from __future__ import annotations

from pathlib import Path

from bachbot.encodings.address_maps import address_for_measure, build_measure_address_map, build_measure_map
from bachbot.encodings.alignment import align_editions, compare_measure_spans
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph, VerticalitySlice
from bachbot.encodings.normalize import normalize_file


class Normalizer:
    def normalize(self, path: str | Path, work_id: str | None = None, encoding_id: str | None = None) -> EventGraph:
        return normalize_file(path, work_id=work_id, encoding_id=encoding_id)


__all__ = [
    "EncodingMetadata",
    "EventGraph",
    "Normalizer",
    "VerticalitySlice",
    "address_for_measure",
    "align_editions",
    "build_measure_address_map",
    "build_measure_map",
    "compare_measure_spans",
    "normalize_file",
]
