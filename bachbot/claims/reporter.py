from __future__ import annotations

from bachbot.claims.bundle import EvidenceBundle


def render_markdown_report(bundle: EvidenceBundle) -> str:
    lines = [
        f"# Evidence Bundle {bundle.bundle_id}",
        "",
        f"- Work: `{bundle.work_id}`",
        f"- Section: `{bundle.section_id}`",
        f"- Genre: `{bundle.metadata.genre}`",
        f"- Key: `{bundle.metadata.key or 'unknown'}`",
        f"- Catalog revision: `{bundle.metadata.catalog_revision}`",
        "",
        "## Deterministic Findings",
        "",
        f"- Harmonic events: `{len(bundle.deterministic_findings.get('harmony', []))}`",
        f"- Cadences: `{len(bundle.deterministic_findings.get('cadences', []))}`",
        f"- Uncertainties: `{len(bundle.uncertainties)}`",
    ]
    if bundle.uncertainties:
        lines.extend(["", "## Uncertainties", ""])
        lines.extend([f"- {item}" for item in bundle.uncertainties])
    return "\n".join(lines)
