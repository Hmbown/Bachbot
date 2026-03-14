from __future__ import annotations

from pydantic import BaseModel, Field

from bachbot.analysis.pipeline import AnalysisReport
from bachbot.claims.uncertainty import collect_uncertainties
from bachbot.encodings.address_maps import build_measure_address_map
from bachbot.encodings.event_graph import EventGraph


class BundleMetadata(BaseModel):
    genre: str
    catalog_revision: str = "BWV3"
    key: str | None = None
    key_tonic: str | None = None
    key_mode: str | None = None
    encoding_id: str


class EvidenceBundle(BaseModel):
    bundle_id: str
    work_id: str
    section_id: str
    passage_refs: list[dict] = Field(default_factory=list)
    metadata: BundleMetadata
    deterministic_findings: dict = Field(default_factory=dict)
    uncertainties: list[str] = Field(default_factory=list)
    provenance: list[dict] = Field(default_factory=list)


def build_evidence_bundle(graph: EventGraph, report: AnalysisReport) -> EvidenceBundle:
    refs = build_measure_address_map(graph)
    key_estimate = graph.metadata.key_estimate
    return EvidenceBundle(
        bundle_id=f"EB-{report.work_id}-{report.section_id}",
        work_id=report.work_id,
        section_id=report.section_id,
        passage_refs=[{"measure_start": ref.measure_number_logical, "measure_end": ref.measure_number_logical, "voice_ids": ref.voice_ids} for ref in refs],
        metadata=BundleMetadata(
            genre=report.genre,
            catalog_revision="BWV3",
            key=report.key,
            key_tonic=key_estimate.tonic if key_estimate else None,
            key_mode=key_estimate.mode if key_estimate else None,
            encoding_id=report.encoding_id,
        ),
        deterministic_findings={
            "cadences": [item.model_dump(mode="json") for item in report.cadences],
            "voice_leading": report.voice_leading,
            "harmony": [item.model_dump(mode="json") for item in report.harmony],
            "phrase_endings": report.phrase_endings,
            "fugue": report.fugue,
            "distributions": report.distributions,
            "anomalies": report.anomalies,
            "validation_report": report.validation_report,
            "modulation_graph": report.modulation_graph,
            "harmonic_rhythm": report.harmonic_rhythm,
            "schenkerian": report.schenkerian,
            "text_music": report.text_music,
            "claims": [item.model_dump(mode="json") for item in report.claims],
        },
        uncertainties=collect_uncertainties(report),
        provenance=[{"source": "encoding", "encoding_id": graph.metadata.encoding_id, "source_path": graph.metadata.source_path}],
    )
