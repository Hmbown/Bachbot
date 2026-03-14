from __future__ import annotations

from typing import Any, Protocol, TypeAlias, runtime_checkable

from bachbot.encodings.event_graph import EventGraph

AnalysisResult: TypeAlias = dict[str, Any]
GenerationResult: TypeAlias = tuple[EventGraph, list[str]]


@runtime_checkable
class AnalyzerPlugin(Protocol):
    plugin_name: str
    plugin_type: str
    description: str
    builtin: bool

    def analyze(self, graph: EventGraph) -> AnalysisResult:
        ...


@runtime_checkable
class GeneratorPlugin(Protocol):
    plugin_name: str
    plugin_type: str
    description: str
    builtin: bool

    def generate(
        self,
        graph: EventGraph,
        *,
        artifact_id: str = "ART-00001",
        bundle: dict[str, Any] | None = None,
    ) -> GenerationResult:
        ...
