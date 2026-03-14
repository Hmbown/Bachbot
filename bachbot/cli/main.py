from __future__ import annotations

import argparse
import sys

import typer

from bachbot import __version__
from bachbot.cli.analyze import app as analyze_app
from bachbot.cli.compose import app as compose_app
from bachbot.cli.corpus import app as corpus_app
from bachbot.cli.detective import app as detective_app
from bachbot.cli.export import app as export_app
from bachbot.cli.llm import app as llm_app
from bachbot.cli.plugins import app as plugins_app
from bachbot.cli.benchmark import app as benchmark_app
from bachbot.cli.evaluate import app as evaluate_app
from bachbot.cli.validate import app as validate_app

app = typer.Typer(help="Bachbot deterministic Bach research and composition CLI.", no_args_is_help=True)
app.add_typer(corpus_app, name="corpus")
app.add_typer(analyze_app, name="analyze")
app.add_typer(compose_app, name="compose")
app.add_typer(validate_app, name="validate")
app.add_typer(detective_app, name="detective")
app.add_typer(export_app, name="export")
app.add_typer(llm_app, name="llm")
app.add_typer(plugins_app, name="plugins")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(evaluate_app, name="evaluate")


def _direct_export(argv: list[str]) -> int | None:
    if not argv or argv[0] != "export":
        return None
    if any(flag in argv[1:] for flag in {"--help", "-h"}):
        return None
    if len(argv) > 1 and argv[1] in {"report", "dataset", "midi"}:
        return None

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--format", default="")
    parser.add_argument("--output", "-o")
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("score")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit:
        return None
    if args.format.lower() != "lilypond":
        return None

    from pathlib import Path

    from bachbot.cli.export import _default_lilypond_output, _load_event_graph
    from bachbot.exports import compile_lilypond, write_lilypond

    graph = _load_event_graph(args.score)
    output_path = Path(args.output) if args.output else _default_lilypond_output(args.score)
    write_lilypond(graph, output_path)
    typer.echo(f"LilyPond: {output_path}")
    if args.pdf:
        pdf_path = compile_lilypond(output_path)
        typer.echo(f"PDF: {pdf_path}")
    return 0


def _version_callback(value: bool) -> None:
    if not value:
        return
    typer.echo(f"bachbot {__version__}")
    raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."),
) -> None:
    del version


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface for the REST API."),
    port: int = typer.Option(8000, "--port", min=1, max=65535, help="Port for the REST API."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for local API development."),
) -> None:
    """Start the FastAPI server."""

    from bachbot.cli.serve import serve_api

    serve_api(host=host, port=port, reload=reload)


def run() -> None:
    exit_code = _direct_export(sys.argv[1:])
    if exit_code is not None:
        raise SystemExit(exit_code)
    app()


if __name__ == "__main__":
    run()
