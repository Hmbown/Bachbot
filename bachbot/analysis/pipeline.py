from __future__ import annotations

from pydantic import BaseModel, Field

from bachbot.analysis.chorale.satb import analyze_chorale_texture
from bachbot.analysis.counterpoint.rules import analyze_counterpoint
from bachbot.analysis.counterpoint.voiceleading import summarize_outer_voice_motion
from bachbot.analysis.form.phrase import infer_phrase_endings
from bachbot.analysis.graphs.modulation_graph import build_modulation_graph
from bachbot.analysis.rhythm.harmonic_rhythm import extract_harmonic_rhythm_from_events
from bachbot.analysis.schenker import analyze_schenkerian
from bachbot.analysis.stats.anomaly import measure_anomaly_scores
from bachbot.analysis.stats.distributions import summarize_distributions
from bachbot.analysis.text_music import analyze_text_music
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.cadence import Cadence
from bachbot.models.claim import AnalyticalClaim, EvidenceRef
from bachbot.models.harmonic_event import HarmonicEvent
from bachbot.models.base import EvidenceStatus
from bachbot.plugins.registry import get_plugin_registry


class AnalysisReport(BaseModel):
    work_id: str
    encoding_id: str
    section_id: str
    genre: str
    key: str | None = None
    harmony: list[HarmonicEvent] = Field(default_factory=list)
    cadences: list[Cadence] = Field(default_factory=list)
    voice_leading: dict = Field(default_factory=dict)
    phrase_endings: list[dict] = Field(default_factory=list)
    fugue: dict = Field(default_factory=dict)
    distributions: dict = Field(default_factory=dict)
    anomalies: dict = Field(default_factory=dict)
    validation_report: dict = Field(default_factory=dict)
    modulation_graph: dict = Field(default_factory=dict)
    harmonic_rhythm: dict = Field(default_factory=dict)
    schenkerian: dict = Field(default_factory=dict)
    text_music: dict = Field(default_factory=dict)
    claims: list[AnalyticalClaim] = Field(default_factory=list)

    @property
    def harmonic_events(self) -> list[HarmonicEvent]:
        return self.harmony


def _format_key(graph: EventGraph) -> str | None:
    if graph.metadata.key_estimate is None:
        return None
    return f"{graph.metadata.key_estimate.tonic} {graph.metadata.key_estimate.mode}"


def _summarize_generic_voice_leading(graph: EventGraph) -> dict[str, object]:
    return {
        **summarize_outer_voice_motion(graph),
        "counterpoint": analyze_counterpoint(graph),
    }


def _build_claims(report: AnalysisReport) -> list[AnalyticalClaim]:
    evidence_refs = [EvidenceRef(ref_id=item.ref_id, description="harmonic event") for item in report.harmony[:3]]
    claims = [
        AnalyticalClaim(
            claim_id=f"CLAIM-{report.encoding_id}-cadence-summary",
            claim_type="analysis_summary",
            lens="harmonic/tonal",
            statement=f"Detected {len(report.cadences)} cadence candidate(s) across {len(report.harmonic_events)} harmonic event(s).",
            status=EvidenceStatus.SUPPORTED_FACT,
            evidence_refs=evidence_refs,
            confidence=0.8,
        )
    ]
    if report.voice_leading:
        claims.append(
            AnalyticalClaim(
                claim_id=f"CLAIM-{report.encoding_id}-voiceleading-summary",
                claim_type="voiceleading_summary",
                lens="counterpoint/voice-leading",
                statement=(
                    f"Detected {report.voice_leading.get('similar', 0)} similar-motion transition(s) "
                    f"with {report.voice_leading.get('counterpoint', {}).get('parallel_5ths', 0)} parallel fifth(s) "
                    f"and {report.voice_leading.get('counterpoint', {}).get('parallel_8ves', 0)} parallel octave(s)."
                ),
                status=EvidenceStatus.SUPPORTED_FACT,
                evidence_refs=evidence_refs[:1],
                confidence=0.75,
            )
        )
    return claims


def analyze_chorale(graph: EventGraph) -> AnalysisReport:
    from bachbot.composition.validators.hard_rules import validate_graph

    registry = get_plugin_registry()
    harmony_plugin = registry.get_analyzer("bachbot.harmony")
    counterpoint_plugin = registry.get_analyzer("bachbot.counterpoint.chorale")

    harmony_result = harmony_plugin.analyze(graph)
    harmony = harmony_result["harmony"]
    cadences = harmony_result["cadences"]
    mod_graph = build_modulation_graph(graph)
    phrase_endings_data = infer_phrase_endings(graph, cadences=cadences)
    phrase_end_ms = [item["measure"] for item in phrase_endings_data]
    hr_profile = extract_harmonic_rhythm_from_events(
        harmony,
        meter=graph.meter,
        phrase_end_measures=phrase_end_ms,
        encoding_id=graph.metadata.encoding_id,
    )
    schenkerian = analyze_schenkerian(
        graph,
        harmony=harmony,
        cadences=cadences,
        phrase_endings=phrase_endings_data,
    )
    text_music = analyze_text_music(graph)
    report = AnalysisReport(
        work_id=graph.work_id,
        encoding_id=graph.metadata.encoding_id,
        section_id=graph.section.section_id,
        genre="chorale",
        key=_format_key(graph),
        harmony=harmony,
        cadences=cadences,
        voice_leading=counterpoint_plugin.analyze(graph)["voice_leading"],
        phrase_endings=phrase_endings_data,
        distributions=summarize_distributions(graph),
        anomalies=measure_anomaly_scores(graph),
        validation_report=validate_graph(graph).model_dump(mode="json"),
        modulation_graph=mod_graph.model_dump(mode="json"),
        harmonic_rhythm=hr_profile.model_dump(mode="json"),
        schenkerian=schenkerian.model_dump(mode="json"),
        text_music=text_music.model_dump(mode="json"),
    )
    report.claims = _build_claims(report)
    return report


def analyze_fugue_exposition(graph: EventGraph) -> AnalysisReport:
    from bachbot.analysis.fugue.answer import detect_real_or_tonal_answers
    from bachbot.analysis.fugue.countersubject import detect_countersubjects
    from bachbot.analysis.fugue.episodes import segment_episodes
    from bachbot.analysis.fugue.stretto import scan_stretto_windows
    from bachbot.analysis.fugue.subject import detect_subject_candidates

    registry = get_plugin_registry()
    harmony_plugin = registry.get_analyzer("bachbot.harmony")
    counterpoint_plugin = registry.get_analyzer("bachbot.counterpoint.generic")
    harmony_result = harmony_plugin.analyze(graph)

    report = AnalysisReport(
        work_id=graph.work_id,
        encoding_id=graph.metadata.encoding_id,
        section_id=graph.section.section_id,
        genre="fugue",
        key=_format_key(graph),
        harmony=harmony_result["harmony"],
        cadences=harmony_result["cadences"],
        voice_leading=counterpoint_plugin.analyze(graph)["voice_leading"],
        fugue={
            "subjects": detect_subject_candidates(graph),
            "answers": detect_real_or_tonal_answers(graph),
            "countersubjects": detect_countersubjects(graph),
            "stretto": scan_stretto_windows(graph),
            "episodes": segment_episodes(graph),
        },
        distributions=summarize_distributions(graph),
        anomalies=measure_anomaly_scores(graph),
    )
    report.claims = _build_claims(report)
    return report


def analyze_graph(graph: EventGraph) -> AnalysisReport:
    label = f"{graph.section.section_type} {graph.title}".lower()
    if "fugue" in label:
        return analyze_fugue_exposition(graph)
    return analyze_chorale(graph)
