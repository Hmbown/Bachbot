from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from bachbot.exports import export_json


def emit_json(payload: dict[str, Any], output: Path | None = None) -> None:
    if output is None:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    export_json(payload, output)
    typer.echo(str(output))
