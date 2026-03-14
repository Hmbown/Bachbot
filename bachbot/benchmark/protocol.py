"""BenchBench task protocol and result models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import BachbotModel, TypedNote


class TaskInput(BachbotModel):
    """What a benchmark task provides to the solver."""

    task_id: str
    task_type: str
    input_notes: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    extra: dict[str, Any] = {}


class TaskOutput(BachbotModel):
    """What the solver returns."""

    task_id: str
    output_notes: list[dict[str, Any]] = []
    output_labels: list[str] = []
    confidence: float = 1.0


class TaskResult(BachbotModel):
    """Scored result for one task instance."""

    task_id: str
    task_type: str
    chorale_id: str
    metrics: dict[str, float] = {}
    passed: bool = False


class SuiteResult(BachbotModel):
    """Full benchmark result."""

    suite_version: str = "1.0.0"
    timestamp: str = ""
    solver_name: str = ""
    split: str = "test"
    task_summaries: dict[str, dict[str, float]] = {}
    per_instance: list[TaskResult] = []
    corpus_size: int = 0


# ── Voice ID normalization ────────────────────────────────────────────

VOICE_NORMALIZE: dict[str, str] = {
    "S": "soprano", "A": "alto", "T": "tenor", "B": "bass",
    "Soprano:1": "soprano", "Alto:1": "alto", "Tenor:1": "tenor", "Bass:1": "bass",
    "Soprano": "soprano", "Alto": "alto", "Tenor": "tenor", "Bass": "bass",
    "soprano": "soprano", "alto": "alto", "tenor": "tenor", "bass": "bass",
}

ROLE_TO_CANDIDATES: dict[str, list[str]] = {
    "soprano": ["Soprano:1", "S", "soprano", "Soprano"],
    "alto": ["Alto:1", "A", "alto", "Alto"],
    "tenor": ["Tenor:1", "T", "tenor", "Tenor"],
    "bass": ["Bass:1", "B", "bass", "Bass"],
}


def resolve_voice(by_voice: dict[str, list], role: str) -> str | None:
    """Find the first matching voice ID for a role."""
    for candidate in ROLE_TO_CANDIDATES.get(role, []):
        if candidate in by_voice and by_voice[candidate]:
            return candidate
    return None


def extract_voice_notes(graph: EventGraph, role: str) -> list[TypedNote]:
    """Extract pitched notes for a voice role, sorted by onset."""
    by_voice = graph.notes_by_voice()
    vid = resolve_voice(by_voice, role)
    if not vid:
        return []
    return sorted(
        [n for n in by_voice[vid] if n.midi is not None and not n.is_rest],
        key=lambda n: n.offset_quarters,
    )


def truncate_graph(graph: EventGraph, max_onset: float) -> EventGraph:
    """Return a new EventGraph with only notes starting before max_onset."""
    kept = [n for n in graph.notes if n.offset_quarters < max_onset]
    return graph.model_copy(update={"notes": kept})


class BenchTask(ABC):
    """Abstract base class for benchmark tasks."""

    task_type: str = ""

    @abstractmethod
    def generate_instances(
        self,
        graphs: list[EventGraph],
        bundles: list[dict],
        split_ids: set[str],
    ) -> list[tuple[TaskInput, EventGraph, dict]]:
        """Generate task instances. Returns (input, ground_truth_graph, bundle)."""
        ...

    @abstractmethod
    def evaluate(
        self,
        task_input: TaskInput,
        task_output: TaskOutput,
        ground_truth: EventGraph,
        bundle: dict,
    ) -> TaskResult:
        """Score a solution against ground truth."""
        ...

    @abstractmethod
    def run_baseline(
        self,
        task_input: TaskInput,
        bundle: dict | None = None,
    ) -> TaskOutput:
        """Run Bachbot's own solver as baseline."""
        ...
