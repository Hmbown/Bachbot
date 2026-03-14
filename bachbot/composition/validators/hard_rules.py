from __future__ import annotations

from bachbot.analysis.chorale.satb import analyze_chorale_texture
from bachbot.analysis.harmony.cadence import detect_cadences
from bachbot.encodings.event_graph import EventGraph
from bachbot.models.evaluation import ValidationIssue, ValidationReport


def validate_graph(graph: EventGraph) -> ValidationReport:
    texture = analyze_chorale_texture(graph)
    cadences = detect_cadences(graph)
    issues: list[ValidationIssue] = []

    for item in texture.get("range_issues", []):
        issues.append(
            ValidationIssue(
                code="range",
                severity="error",
                message=f"Voice {item['voice']} exceeds SATB range.",
                measure=item.get("measure"),
                voice_ids=[item["voice"]],
            )
        )

    for item in texture.get("spacing_issues", []):
        issues.append(
            ValidationIssue(
                code="spacing",
                severity="error",
                message=f"Spacing violation between {item['voices']}.",
                measure=item.get("measure"),
                voice_ids=item.get("voices", "").split("|"),
            )
        )

    counterpoint = texture.get("counterpoint", {})
    if counterpoint.get("parallel_5ths", 0):
        issues.append(
            ValidationIssue(
                code="parallel_5ths",
                severity="error",
                message="Parallel fifths detected.",
            )
        )
    if counterpoint.get("parallel_8ves", 0):
        issues.append(
            ValidationIssue(
                code="parallel_8ves",
                severity="error",
                message="Parallel octaves detected.",
            )
        )
    if not cadences:
        issues.append(
            ValidationIssue(
                code="cadence_missing",
                severity="warning",
                message="No cadence candidates detected.",
            )
        )

    passed = not any(issue.severity == "error" for issue in issues)
    return ValidationReport(
        validation_id=f"VAL-{graph.metadata.encoding_id}",
        subject_type="event_graph",
        subject_id=graph.metadata.encoding_id,
        passed=passed,
        issues=issues,
    )


def validate_generated_chorale(graph: EventGraph) -> dict[str, object]:
    report = validate_graph(graph)
    return {
        "ok": report.passed,
        "cadence_count": len(detect_cadences(graph)),
        "issues": [issue.model_dump(mode="json") for issue in report.issues],
    }
