"""Plugin management CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from bachbot.cli.io import emit_json
from bachbot.plugins.registry import refresh_plugin_registry

app = typer.Typer(help="Inspect installed analyzer and generator plugins.")


@app.command("list")
def list_plugins(
    output: Path | None = typer.Option(None, "--output", help="Write the plugin inventory JSON to a file instead of stdout."),
) -> None:
    """List built-in and externally discovered Bachbot plugins."""

    registry = refresh_plugin_registry()
    emit_json(
        {
            "plugins": [
                {
                    "name": plugin.name,
                    "type": plugin.type,
                    "description": plugin.description,
                    "builtin": plugin.builtin,
                    "source": plugin.source,
                }
                for plugin in registry.list_plugins()
            ],
            "discovery_errors": [
                {
                    "group": error.group,
                    "entry_point": error.entry_point,
                    "message": error.message,
                }
                for error in registry.discovery_errors
            ],
        },
        output=output,
    )
