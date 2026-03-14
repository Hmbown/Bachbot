from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from typing import Any

from bachbot.plugins.protocols import AnalyzerPlugin, GeneratorPlugin

ANALYZER_ENTRYPOINT_GROUP = "bachbot.analyzers"
GENERATOR_ENTRYPOINT_GROUP = "bachbot.generators"


@dataclass(slots=True)
class DiscoveryError:
    group: str
    entry_point: str
    message: str


def _iter_entry_points(group: str) -> list[Any]:
    entry_points = importlib_metadata.entry_points()
    if hasattr(entry_points, "select"):
        return list(entry_points.select(group=group))
    return list(entry_points.get(group, []))


def _is_analyzer_plugin(candidate: object) -> bool:
    return (
        hasattr(candidate, "plugin_name")
        and getattr(candidate, "plugin_type", None) == "analyzer"
        and callable(getattr(candidate, "analyze", None))
    )


def _is_generator_plugin(candidate: object) -> bool:
    return (
        hasattr(candidate, "plugin_name")
        and getattr(candidate, "plugin_type", None) == "generator"
        and callable(getattr(candidate, "generate", None))
    )


def _resolve_plugin(entry_point: Any, *, plugin_type: str) -> AnalyzerPlugin | GeneratorPlugin:
    loaded = entry_point.load()
    if plugin_type == "analyzer":
        if _is_analyzer_plugin(loaded):
            return loaded
        if callable(loaded):
            instance = loaded()
            if _is_analyzer_plugin(instance):
                return instance
        raise TypeError(f"Entry point {entry_point.name!r} did not resolve to an analyzer plugin")

    if _is_generator_plugin(loaded):
        return loaded
    if callable(loaded):
        instance = loaded()
        if _is_generator_plugin(instance):
            return instance
    raise TypeError(f"Entry point {entry_point.name!r} did not resolve to a generator plugin")


def load_analyzer_entry_points() -> tuple[list[AnalyzerPlugin], list[DiscoveryError]]:
    plugins: list[AnalyzerPlugin] = []
    errors: list[DiscoveryError] = []
    for entry_point in _iter_entry_points(ANALYZER_ENTRYPOINT_GROUP):
        try:
            plugin = _resolve_plugin(entry_point, plugin_type="analyzer")
        except Exception as exc:
            errors.append(DiscoveryError(group=ANALYZER_ENTRYPOINT_GROUP, entry_point=entry_point.name, message=str(exc)))
            continue
        plugins.append(plugin)
    return plugins, errors


def load_generator_entry_points() -> tuple[list[GeneratorPlugin], list[DiscoveryError]]:
    plugins: list[GeneratorPlugin] = []
    errors: list[DiscoveryError] = []
    for entry_point in _iter_entry_points(GENERATOR_ENTRYPOINT_GROUP):
        try:
            plugin = _resolve_plugin(entry_point, plugin_type="generator")
        except Exception as exc:
            errors.append(DiscoveryError(group=GENERATOR_ENTRYPOINT_GROUP, entry_point=entry_point.name, message=str(exc)))
            continue
        plugins.append(plugin)
    return plugins, errors
