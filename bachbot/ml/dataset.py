from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import numpy as np

from bachbot.encodings import Normalizer
from bachbot.encodings.event_graph import EventGraph
from bachbot.encodings.tensors import build_chord_vocabulary

try:
    import torch
    from torch.utils.data import Dataset as TorchDataset
except ImportError:  # pragma: no cover - exercised in environments without torch
    torch = None

    class TorchDataset:  # type: ignore[too-many-ancestors]
        pass


RepresentationName = Literal["piano_roll", "voice_tensor", "chord_sequence"]


def _require_torch():
    if torch is None:
        raise ImportError("BachDataset requires torch; install bachbot with the [ml] extra")
    return torch


def _coerce_graph(item: EventGraph | str | Path) -> EventGraph:
    if isinstance(item, EventGraph):
        return item
    return Normalizer().normalize(Path(item))


def _infer_pitch_range(graphs: Sequence[EventGraph]) -> tuple[int, int]:
    midis = [note.midi for graph in graphs for note in graph.notes if note.midi is not None and not note.is_rest]
    if not midis:
        return (0, 127)
    return (min(midis), max(midis))


def _infer_voice_order(graphs: Sequence[EventGraph]) -> list[str]:
    seen: list[str] = []
    for graph in graphs:
        for voice_id in graph.ordered_voice_ids():
            if voice_id not in seen:
                seen.append(voice_id)
    return seen


class BachDataset(TorchDataset):
    def __init__(
        self,
        items: Sequence[EventGraph | str | Path],
        *,
        representation: RepresentationName = "piano_roll",
        resolution: int = 4,
        pitch_range: tuple[int, int] | None = None,
        voice_order: Sequence[str] | None = None,
        vocabulary: Sequence[str] | None = None,
    ) -> None:
        _require_torch()
        self.graphs = [_coerce_graph(item) for item in items]
        self.representation = representation
        self.resolution = resolution
        self.pitch_range = pitch_range or _infer_pitch_range(self.graphs)
        self.voice_order = list(voice_order or _infer_voice_order(self.graphs))
        self.vocabulary = list(vocabulary) if vocabulary is not None else (
            build_chord_vocabulary(self.graphs) if representation == "chord_sequence" else []
        )

    def __len__(self) -> int:
        return len(self.graphs)

    def __getitem__(self, index: int):
        graph = self.graphs[index]
        if self.representation == "piano_roll":
            array = graph.to_piano_roll(resolution=self.resolution)
        elif self.representation == "voice_tensor":
            array = graph.to_voice_tensor(
                resolution=self.resolution,
                pitch_range=self.pitch_range,
                voice_order=self.voice_order,
            )
        elif self.representation == "chord_sequence":
            array = graph.to_chord_sequence(vocabulary=self.vocabulary)
        else:  # pragma: no cover - protected by type hints in normal use
            raise ValueError(f"Unsupported representation: {self.representation}")
        return _require_torch().from_numpy(np.asarray(array, dtype=np.float32))
