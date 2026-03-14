from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bachbot.claims.bundle import EvidenceBundle
from bachbot.models.annotation import (
    AnnotatedFinding,
    AnnotationAgreement,
    AnnotationConflict,
    AnnotationDiff,
    AnnotationDiffSummary,
    AnnotationFindingTypeSummary,
    AnnotationLayer,
    AnnotationSource,
)
from bachbot.models.base import EvidenceStatus
from bachbot.models.refs import PassageRef

MEASURE_RE = re.compile(r"m(\d+)$")


def bundle_to_annotation_layer(bundle: EvidenceBundle | dict[str, Any]) -> AnnotationLayer:
    bundle_model = bundle if isinstance(bundle, EvidenceBundle) else EvidenceBundle.model_validate(bundle)
    source = AnnotationSource(
        source_id=f"bachbot:{bundle_model.bundle_id}",
        source_type="bachbot",
        label="bachbot",
        version=bundle_model.metadata.catalog_revision,
        provenance=[json.dumps(item, sort_keys=True) for item in bundle_model.provenance],
    )
    findings: list[AnnotatedFinding] = []

    for index, item in enumerate(bundle_model.deterministic_findings.get("harmony", [])):
        measure = _measure_from_ref_id(str(item.get("ref_id", "")))
        findings.append(
            AnnotatedFinding(
                finding_id=str(item.get("harmonic_event_id", f"{bundle_model.bundle_id}:harmony:{index}")),
                finding_type="harmony",
                passage_ref=PassageRef(measure_start=measure, measure_end=measure, voice_ids=[]),
                value={
                    "roman_numeral": _first(item.get("roman_numeral_candidate_set")),
                    "candidate_set": list(item.get("roman_numeral_candidate_set", [])),
                    "onset": _float_or_none(item.get("onset")),
                },
                status=EvidenceStatus.SUPPORTED_FACT,
                confidence=float(item.get("confidence", 0.0) or 0.0),
                source_id=source.source_id,
            )
        )

    for index, item in enumerate(bundle_model.deterministic_findings.get("cadences", [])):
        measure = _measure_from_ref_id(str(item.get("ref_id", "")))
        findings.append(
            AnnotatedFinding(
                finding_id=str(item.get("cadence_id", f"{bundle_model.bundle_id}:cadence:{index}")),
                finding_type="cadence",
                passage_ref=PassageRef(measure_start=measure, measure_end=measure, voice_ids=[]),
                value={
                    "cadence_type": item.get("cadence_type"),
                    "bass_formula": item.get("bass_formula"),
                    "soprano_formula": item.get("soprano_formula"),
                },
                status=EvidenceStatus.SUPPORTED_FACT,
                confidence=float(item.get("detector_confidence", 0.0) or 0.0),
                source_id=source.source_id,
            )
        )

    return AnnotationLayer(
        layer_id=f"AL-{bundle_model.bundle_id}",
        work_id=bundle_model.work_id,
        section_id=bundle_model.section_id,
        source=source,
        findings=findings,
    )


def load_annotation_layer(path: str | Path) -> AnnotationLayer:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "bundle_id" in payload and "deterministic_findings" in payload:
        return bundle_to_annotation_layer(payload)
    if isinstance(payload, dict) and "layer_id" in payload and "findings" in payload:
        return AnnotationLayer.model_validate(payload)
    raise ValueError("Annotation JSON must be an EvidenceBundle or AnnotationLayer payload.")


def compare_annotation_layers(left: AnnotationLayer, right: AnnotationLayer) -> AnnotationDiff:
    left_index = {finding_key(item): item for item in left.findings}
    right_index = {finding_key(item): item for item in right.findings}
    matches: list[AnnotationAgreement] = []
    conflicts: list[AnnotationConflict] = []
    left_only: list[AnnotatedFinding] = []
    right_only: list[AnnotatedFinding] = []

    for key in sorted(set(left_index) | set(right_index), key=str):
        left_item = left_index.get(key)
        right_item = right_index.get(key)
        if left_item and right_item:
            left_value = canonical_value(left_item)
            right_value = canonical_value(right_item)
            if left_value == right_value:
                matches.append(
                    AnnotationAgreement(
                        passage_ref=left_item.passage_ref,
                        finding_type=left_item.finding_type,
                        value=left_value,
                        left_source=left.source.label,
                        right_source=right.source.label,
                    )
                )
            else:
                conflicts.append(
                    AnnotationConflict(
                        passage_ref=left_item.passage_ref,
                        finding_type=left_item.finding_type,
                        left_value=left_value,
                        right_value=right_value,
                        left_source=left.source.label,
                        right_source=right.source.label,
                    )
                )
            continue
        if left_item:
            left_only.append(left_item)
        if right_item:
            right_only.append(right_item)

    diff = AnnotationDiff(
        left_source=left.source,
        right_source=right.source,
        matches=matches,
        conflicts=conflicts,
        left_only=left_only,
        right_only=right_only,
    )
    diff.summary = summarize_annotation_diff(diff)
    return diff


def summarize_annotation_diff(diff: AnnotationDiff) -> AnnotationDiffSummary:
    by_type: dict[str, AnnotationFindingTypeSummary] = {}

    def _bucket(finding_type: str) -> AnnotationFindingTypeSummary:
        if finding_type not in by_type:
            by_type[finding_type] = AnnotationFindingTypeSummary()
        return by_type[finding_type]

    for item in diff.matches:
        _bucket(item.finding_type).match_count += 1
    for item in diff.conflicts:
        _bucket(item.finding_type).conflict_count += 1
    for item in diff.left_only:
        _bucket(item.finding_type).left_only_count += 1
    for item in diff.right_only:
        _bucket(item.finding_type).right_only_count += 1

    overlap_count = len(diff.matches) + len(diff.conflicts)
    return AnnotationDiffSummary(
        match_count=len(diff.matches),
        conflict_count=len(diff.conflicts),
        left_only_count=len(diff.left_only),
        right_only_count=len(diff.right_only),
        overlap_count=overlap_count,
        agreement_ratio=round(len(diff.matches) / overlap_count, 3) if overlap_count else 0.0,
        by_finding_type={key: by_type[key] for key in sorted(by_type)},
    )


def finding_key(finding: AnnotatedFinding) -> tuple[object, ...]:
    onset = finding.value.get("onset")
    onset_value = round(float(onset), 3) if isinstance(onset, (int, float)) else None
    return (
        finding.finding_type,
        finding.passage_ref.measure_start,
        finding.passage_ref.measure_end,
        tuple(sorted(finding.passage_ref.voice_ids)),
        onset_value,
    )


def canonical_value(finding: AnnotatedFinding) -> dict[str, object]:
    if finding.finding_type == "harmony":
        return {"roman_numeral": finding.value.get("roman_numeral")}
    if finding.finding_type == "cadence":
        return {"cadence_type": finding.value.get("cadence_type")}
    return dict(finding.value)


def _measure_from_ref_id(ref_id: str) -> int:
    match = MEASURE_RE.search(ref_id)
    if match:
        return int(match.group(1))
    return 1


def _first(value: object) -> object:
    if isinstance(value, list) and value:
        return value[0]
    return None


def load_dcml_annotation_layer(work_id: str, *, derived_dir: Path | None = None) -> AnnotationLayer:
    """Load a DCML evidence bundle as an annotation layer by work_id."""
    derived_dir = derived_dir or Path("data/derived/dcml_bach_chorales")
    if not derived_dir.is_dir():
        raise FileNotFoundError(
            f"DCML derived directory not found: {derived_dir}"
        )
    for bundle_path in derived_dir.glob("*.evidence_bundle.json"):
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        if payload.get("work_id") == work_id:
            layer = bundle_to_annotation_layer(payload)
            layer.source = AnnotationSource(
                source_id=f"dcml:{work_id}",
                source_type="dcml",
                label="dcml",
                version="dcml_bach_chorales",
                provenance=[f"file:{bundle_path.name}"],
            )
            return layer
    raise FileNotFoundError(
        f"No DCML evidence bundle found for work_id={work_id!r}"
    )


def _float_or_none(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None
