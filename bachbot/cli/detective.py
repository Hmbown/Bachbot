"""Detective-mode CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from bachbot.analysis import analyze_graph
from bachbot.claims import build_evidence_bundle
from bachbot.cli.io import emit_json
from bachbot.encodings import Normalizer

app = typer.Typer(help="Hypothesis and anomaly scan commands.")


@app.command("scan")
def scan(
    score_path: Path,
    output: Path | None = typer.Option(None, "--output", help="Write the detective summary JSON to a file instead of stdout."),
) -> None:
    """Summarize uncertainties and anomaly-oriented counts for a score."""

    graph = Normalizer().normalize(score_path)
    analysis = analyze_graph(graph)
    bundle = build_evidence_bundle(graph, analysis)
    payload = {
        "work_id": bundle.work_id,
        "bundle_id": bundle.bundle_id,
        "uncertainty_count": len(bundle.uncertainties),
        "cadence_count": len(bundle.deterministic_findings["cadences"]),
        "uncertainties": bundle.uncertainties,
    }
    emit_json(payload, output=output)
