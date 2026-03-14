from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from bachbot.encodings import EventGraph
from bachbot.ml import BachDataset


def test_event_graph_to_piano_roll_respects_resolution(simple_chorale_graph) -> None:
    quarter_steps = simple_chorale_graph.to_piano_roll(resolution=4)
    eighth_steps = simple_chorale_graph.to_piano_roll(resolution=8)

    assert quarter_steps.shape[1] == 128
    assert eighth_steps.shape[1] == 128
    assert eighth_steps.shape[0] == quarter_steps.shape[0] * 2
    assert quarter_steps.sum() > 0


def test_event_graph_to_voice_tensor_preserves_voice_separation(simple_chorale_graph) -> None:
    pitches = [note.midi for note in simple_chorale_graph.notes if note.midi is not None and not note.is_rest]
    pitch_range = (min(pitches), max(pitches))

    voice_tensor = simple_chorale_graph.to_voice_tensor(resolution=4, pitch_range=pitch_range)
    piano_roll = simple_chorale_graph.to_piano_roll(resolution=4)

    assert voice_tensor.shape[1] == len(simple_chorale_graph.ordered_voice_ids())
    np.testing.assert_array_equal(voice_tensor.max(axis=1), piano_roll[:, pitch_range[0] : pitch_range[1] + 1])


def test_piano_roll_round_trip_matches_original(simple_chorale_graph) -> None:
    piano_roll = simple_chorale_graph.to_piano_roll(resolution=8)
    restored = EventGraph.from_piano_roll(
        piano_roll,
        resolution=8,
        metadata=simple_chorale_graph.metadata,
        encoding_id="BWV-TEST-ROLL",
    )

    np.testing.assert_array_equal(restored.to_piano_roll(resolution=8), piano_roll)


def test_bach_dataset_returns_requested_representation(simple_chorale_graph) -> None:
    torch = pytest.importorskip("torch")

    voice_dataset = BachDataset([simple_chorale_graph], representation="voice_tensor", resolution=4)
    voice_item = voice_dataset[0]
    assert isinstance(voice_item, torch.Tensor)
    assert voice_item.ndim == 3

    chord_dataset = BachDataset([simple_chorale_graph], representation="chord_sequence")
    chord_item = chord_dataset[0]
    assert chord_item.ndim == 2
    assert chord_item.shape[1] == len(chord_dataset.vocabulary)
    assert torch.allclose(chord_item.sum(dim=1), torch.ones(chord_item.shape[0]))


def test_example_training_script_runs_on_fixture_corpus(fixture_dir: Path) -> None:
    pytest.importorskip("torch")

    result = subprocess.run(
        [
            sys.executable,
            "examples/train_chord_rnn.py",
            str(fixture_dir / "chorales"),
            "--pattern",
            "*.musicxml",
            "--limit",
            "2",
            "--epochs",
            "1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "epoch=1" in result.stdout
