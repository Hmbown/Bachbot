from __future__ import annotations

import json

from typer.testing import CliRunner

import bachbot.plugins.discovery as plugin_discovery
from bachbot.analysis.chorale.satb import analyze_chorale_texture
from bachbot.analysis.harmony.cadence import detect_cadences, summarize_harmony
from bachbot.analysis.pipeline import analyze_chorale
from bachbot.cli.main import app
from bachbot.composition.generators.pattern_fill import harmonize_chorale_melody
from bachbot.composition.service import compose_chorale_study
from bachbot.plugins import refresh_plugin_registry


class _FakeEntryPoint:
    def __init__(self, *, name: str, group: str, loaded: object) -> None:
        self.name = name
        self.group = group
        self.value = f"{group}:{name}"
        self._loaded = loaded

    def load(self) -> object:
        return self._loaded


class _FakeEntryPoints(list[_FakeEntryPoint]):
    def select(self, *, group: str):  # type: ignore[override]
        return [entry_point for entry_point in self if entry_point.group == group]


class _ExternalAnalyzerPlugin:
    plugin_name = "external.analysis.demo"
    plugin_type = "analyzer"
    description = "Demo external analyzer"
    builtin = False

    def analyze(self, graph):  # type: ignore[no-untyped-def]
        return {"work_id": graph.work_id}


class _ExternalGeneratorPlugin:
    plugin_name = "external.generator.demo"
    plugin_type = "generator"
    description = "Demo external generator"
    builtin = False

    def generate(self, graph, *, artifact_id="ART-00001", bundle=None):  # type: ignore[no-untyped-def]
        del artifact_id, bundle
        return graph, []


class _SpyHarmonyPlugin:
    plugin_name = "bachbot.harmony"
    plugin_type = "analyzer"
    description = "Spy harmony analyzer"
    builtin = True

    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, graph):  # type: ignore[no-untyped-def]
        self.calls += 1
        return {
            "harmony": summarize_harmony(graph),
            "cadences": detect_cadences(graph),
        }


class _SpyCounterpointPlugin:
    plugin_name = "bachbot.counterpoint.chorale"
    plugin_type = "analyzer"
    description = "Spy chorale counterpoint analyzer"
    builtin = True

    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, graph):  # type: ignore[no-untyped-def]
        self.calls += 1
        return {"voice_leading": analyze_chorale_texture(graph)}


class _SpyGeneratorPlugin:
    plugin_name = "bachbot.chorale_harmonizer"
    plugin_type = "generator"
    description = "Spy chorale generator"
    builtin = True

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, graph, *, artifact_id="ART-00001", bundle=None):  # type: ignore[no-untyped-def]
        self.calls += 1
        return harmonize_chorale_melody(graph, artifact_id=artifact_id, bundle=bundle)


class _AnalysisRegistry:
    def __init__(self, harmony_plugin: _SpyHarmonyPlugin, counterpoint_plugin: _SpyCounterpointPlugin) -> None:
        self.harmony_plugin = harmony_plugin
        self.counterpoint_plugin = counterpoint_plugin

    def get_analyzer(self, name: str):  # type: ignore[no-untyped-def]
        if name == "bachbot.harmony":
            return self.harmony_plugin
        if name == "bachbot.counterpoint.chorale":
            return self.counterpoint_plugin
        raise KeyError(name)


class _CompositionRegistry:
    def __init__(self, generator_plugin: _SpyGeneratorPlugin) -> None:
        self.generator_plugin = generator_plugin

    def get_generator(self, name: str):  # type: ignore[no-untyped-def]
        if name == "bachbot.chorale_harmonizer":
            return self.generator_plugin
        raise KeyError(name)


def test_builtin_plugins_are_registered() -> None:
    registry = refresh_plugin_registry()
    plugins = {(plugin.type, plugin.name): plugin for plugin in registry.list_plugins()}

    assert ("analyzer", "bachbot.harmony") in plugins
    assert ("analyzer", "bachbot.counterpoint.chorale") in plugins
    assert ("analyzer", "bachbot.counterpoint.generic") in plugins
    assert ("generator", "bachbot.chorale_harmonizer") in plugins
    assert plugins[("analyzer", "bachbot.harmony")].builtin is True


def test_plugins_cli_lists_entry_point_plugins(monkeypatch) -> None:
    fake_entry_points = _FakeEntryPoints(
        [
            _FakeEntryPoint(
                name="external.analysis.demo",
                group=plugin_discovery.ANALYZER_ENTRYPOINT_GROUP,
                loaded=_ExternalAnalyzerPlugin(),
            ),
            _FakeEntryPoint(
                name="external.generator.demo",
                group=plugin_discovery.GENERATOR_ENTRYPOINT_GROUP,
                loaded=_ExternalGeneratorPlugin(),
            ),
        ]
    )
    monkeypatch.setattr(plugin_discovery.importlib_metadata, "entry_points", lambda: fake_entry_points)

    result = CliRunner().invoke(app, ["plugins", "list"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    names = {plugin["name"] for plugin in payload["plugins"]}
    assert "external.analysis.demo" in names
    assert "external.generator.demo" in names
    assert payload["discovery_errors"] == []


def test_analyze_chorale_uses_plugin_registry(simple_chorale_graph, monkeypatch) -> None:
    harmony_plugin = _SpyHarmonyPlugin()
    counterpoint_plugin = _SpyCounterpointPlugin()
    monkeypatch.setattr(
        "bachbot.analysis.pipeline.get_plugin_registry",
        lambda: _AnalysisRegistry(harmony_plugin, counterpoint_plugin),
    )

    report = analyze_chorale(simple_chorale_graph)

    assert report.harmony
    assert report.voice_leading
    assert harmony_plugin.calls == 1
    assert counterpoint_plugin.calls == 1


def test_compose_chorale_study_uses_plugin_registry(simple_cantus_graph, monkeypatch) -> None:
    generator_plugin = _SpyGeneratorPlugin()
    monkeypatch.setattr(
        "bachbot.composition.service.get_plugin_registry",
        lambda: _CompositionRegistry(generator_plugin),
    )

    graph, artifact, report = compose_chorale_study(simple_cantus_graph)

    assert graph.notes
    assert artifact.artifact_id.startswith("ART-")
    assert report["trace"]
    assert generator_plugin.calls == 2
