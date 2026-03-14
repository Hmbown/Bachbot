from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from bachbot.plugins.builtins import builtin_analyzers, builtin_generators
from bachbot.plugins.discovery import DiscoveryError, load_analyzer_entry_points, load_generator_entry_points
from bachbot.plugins.protocols import AnalyzerPlugin, GeneratorPlugin


@dataclass(slots=True)
class PluginInfo:
    name: str
    type: str
    description: str
    builtin: bool
    source: str


class PluginRegistry:
    def __init__(self) -> None:
        self._analyzers: dict[str, AnalyzerPlugin] = {}
        self._generators: dict[str, GeneratorPlugin] = {}
        self._plugin_info: dict[tuple[str, str], PluginInfo] = {}
        self.discovery_errors: list[DiscoveryError] = []

    def register_analyzer(self, plugin: AnalyzerPlugin, *, source: str) -> None:
        self._analyzers[plugin.plugin_name] = plugin
        self._plugin_info[(plugin.plugin_type, plugin.plugin_name)] = PluginInfo(
            name=plugin.plugin_name,
            type=plugin.plugin_type,
            description=plugin.description,
            builtin=plugin.builtin,
            source=source,
        )

    def register_generator(self, plugin: GeneratorPlugin, *, source: str) -> None:
        self._generators[plugin.plugin_name] = plugin
        self._plugin_info[(plugin.plugin_type, plugin.plugin_name)] = PluginInfo(
            name=plugin.plugin_name,
            type=plugin.plugin_type,
            description=plugin.description,
            builtin=plugin.builtin,
            source=source,
        )

    def get_analyzer(self, name: str) -> AnalyzerPlugin:
        try:
            return self._analyzers[name]
        except KeyError as exc:
            raise KeyError(f"Unknown analyzer plugin: {name}") from exc

    def get_generator(self, name: str) -> GeneratorPlugin:
        try:
            return self._generators[name]
        except KeyError as exc:
            raise KeyError(f"Unknown generator plugin: {name}") from exc

    def list_plugins(self) -> list[PluginInfo]:
        return sorted(self._plugin_info.values(), key=lambda item: (item.type, item.name))


def build_plugin_registry() -> PluginRegistry:
    registry = PluginRegistry()
    for plugin in builtin_analyzers():
        registry.register_analyzer(plugin, source="builtin")
    for plugin in builtin_generators():
        registry.register_generator(plugin, source="builtin")

    analyzers, analyzer_errors = load_analyzer_entry_points()
    for plugin in analyzers:
        registry.register_analyzer(plugin, source="entry_point")
    registry.discovery_errors.extend(analyzer_errors)

    generators, generator_errors = load_generator_entry_points()
    for plugin in generators:
        registry.register_generator(plugin, source="entry_point")
    registry.discovery_errors.extend(generator_errors)
    return registry


@lru_cache(maxsize=1)
def get_plugin_registry() -> PluginRegistry:
    return build_plugin_registry()


def refresh_plugin_registry() -> PluginRegistry:
    get_plugin_registry.cache_clear()
    return get_plugin_registry()
