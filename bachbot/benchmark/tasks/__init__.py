"""BachBench task registry."""

from __future__ import annotations

from bachbot.benchmark.protocol import BenchTask
from bachbot.benchmark.tasks.completion import CompletionTask
from bachbot.benchmark.tasks.harmonization import HarmonizationTask
from bachbot.benchmark.tasks.next_chord import NextChordTask
from bachbot.benchmark.tasks.style_discrimination import StyleDiscriminationTask

TASK_REGISTRY: dict[str, BenchTask] = {
    "harmonization": HarmonizationTask(),
    "next_chord": NextChordTask(),
    "completion": CompletionTask(),
    "style_discrimination": StyleDiscriminationTask(),
}

__all__ = ["TASK_REGISTRY"]
