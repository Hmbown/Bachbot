"""Validation CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from bachbot.cli.io import emit_json
from bachbot.composition.validators.hard_rules import validate_graph
from bachbot.encodings import Normalizer

app = typer.Typer(help="Validation commands.")


@app.command("score")
def validate_score(
    score_path: Path,
    output: Path | None = typer.Option(None, "--output", help="Write the validation report JSON to a file instead of stdout."),
) -> None:
    """Validate a score against Bachbot's hard-rule checks."""

    graph = Normalizer().normalize(score_path)
    emit_json(validate_graph(graph).model_dump(mode="json"), output=output)
