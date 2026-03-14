from __future__ import annotations

from bachbot.encodings.event_graph import EventGraph
from bachbot.plugins.protocols import AnalysisResult, AnalyzerPlugin, GenerationResult, GeneratorPlugin


class HarmonyAnalyzer:
    plugin_name = "bachbot.harmony"
    plugin_type = "analyzer"
    description = "Compute harmonic events and cadence candidates."
    builtin = True

    def analyze(self, graph: EventGraph) -> AnalysisResult:
        from bachbot.analysis.harmony.cadence import detect_cadences, summarize_harmony

        harmony = summarize_harmony(graph)
        return {
            "harmony": harmony,
            "cadences": detect_cadences(graph),
        }


class ChoraleCounterpointAnalyzer:
    plugin_name = "bachbot.counterpoint.chorale"
    plugin_type = "analyzer"
    description = "Compute SATB texture and counterpoint summaries for chorales."
    builtin = True

    def analyze(self, graph: EventGraph) -> AnalysisResult:
        from bachbot.analysis.chorale.satb import analyze_chorale_texture

        return {"voice_leading": analyze_chorale_texture(graph)}


class GenericCounterpointAnalyzer:
    plugin_name = "bachbot.counterpoint.generic"
    plugin_type = "analyzer"
    description = "Compute generic outer-voice motion and counterpoint summaries."
    builtin = True

    def analyze(self, graph: EventGraph) -> AnalysisResult:
        from bachbot.analysis.counterpoint.rules import analyze_counterpoint
        from bachbot.analysis.counterpoint.voiceleading import summarize_outer_voice_motion

        return {
            "voice_leading": {
                **summarize_outer_voice_motion(graph),
                "counterpoint": analyze_counterpoint(graph),
            }
        }


class ChoraleGenerator:
    plugin_name = "bachbot.chorale_harmonizer"
    plugin_type = "generator"
    description = "Constraint-first SATB chorale harmonizer."
    builtin = True

    def generate(
        self,
        graph: EventGraph,
        *,
        artifact_id: str = "ART-00001",
        bundle: dict[str, object] | None = None,
    ) -> GenerationResult:
        from bachbot.composition.generators.pattern_fill import harmonize_chorale_melody

        return harmonize_chorale_melody(graph, artifact_id=artifact_id, bundle=bundle)


def builtin_analyzers() -> list[AnalyzerPlugin]:
    return [
        HarmonyAnalyzer(),
        ChoraleCounterpointAnalyzer(),
        GenericCounterpointAnalyzer(),
    ]


def builtin_generators() -> list[GeneratorPlugin]:
    return [ChoraleGenerator()]
