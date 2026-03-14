"""Export CLI commands."""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer

from bachbot.analysis import analyze_graph
from bachbot.claims import build_evidence_bundle
from bachbot.encodings import Normalizer
from bachbot.encodings.event_graph import EventGraph
from bachbot.exports import compile_lilypond, export_report, write_lilypond
from bachbot.exports.features import (
    extract_features,
    extract_note_sequences,
    export_dataset_csv,
    export_dataset_huggingface,
    export_dataset_json,
)

app = typer.Typer(
    help="Report export commands.",
    context_settings={"allow_extra_args": True},
    invoke_without_command=True,
)


def _load_event_graph(score: str) -> EventGraph:
    candidate = Path(score)
    if candidate.exists():
        if candidate.suffix == ".json":
            return EventGraph.model_validate(json.loads(candidate.read_text(encoding="utf-8")))
        return Normalizer().normalize(candidate)

    match = re.fullmatch(r"BWV-?(\d+)", score, flags=re.IGNORECASE)
    if match:
        number = int(match.group(1))
        normalized = sorted(Path("data/normalized/dcml_bach_chorales").glob(f"notes__{number:03d}*.event_graph.json"))
        if normalized:
            return EventGraph.model_validate(json.loads(normalized[0].read_text(encoding="utf-8")))
        raw = sorted(Path("data/raw/dcml_bach_chorales/notes").glob(f"{number:03d} *.notes.tsv"))
        if raw:
            return Normalizer().normalize(raw[0], work_id=f"BWV-{number:03d}", encoding_id=f"BWV-{number:03d}")
    raise typer.BadParameter(f"Could not resolve score reference: {score}")


def _default_lilypond_output(score: str) -> Path:
    match = re.fullmatch(r"BWV-?(\d+)", score, flags=re.IGNORECASE)
    stem = f"BWV{int(match.group(1)):03d}" if match else Path(score).stem
    return Path("data/derived/exports") / f"{stem}.ly"


@app.callback(invoke_without_command=True)
def export_callback(
    ctx: typer.Context,
    format: str = typer.Option("", "--format", help="Direct export format when no subcommand is used."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Direct export output path."),
    pdf: bool = typer.Option(False, "--pdf", help="Compile LilyPond source to PDF."),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if not ctx.args:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    if len(ctx.args) != 1:
        raise typer.BadParameter("Direct export mode expects exactly one score reference.")
    score = ctx.args[0]
    if format.lower() != "lilypond":
        raise typer.BadParameter("Only --format lilypond is supported in direct export mode.")

    graph = _load_event_graph(score)
    lilypond_path = output or _default_lilypond_output(score)
    write_lilypond(graph, lilypond_path)
    typer.echo(f"LilyPond: {lilypond_path}")
    if pdf:
        pdf_path = compile_lilypond(lilypond_path)
        typer.echo(f"PDF: {pdf_path}")


@app.command("report")
def report(score_path: Path, output: Path = Path("data/derived/report.md")) -> None:
    graph = Normalizer().normalize(score_path)
    analysis = analyze_graph(graph)
    bundle = build_evidence_bundle(graph, analysis)
    export_report(bundle, output)
    typer.echo(str(output))


@app.command("dataset")
def dataset(
    corpus: str = typer.Option("dcml_bach_chorales", help="Corpus name under data/."),
    format: str = typer.Option("csv", help="Output format: csv, json, or huggingface."),
    output: Path = typer.Option(None, help="Output path. Defaults to data/derived/<corpus>/dataset.<ext>."),
    limit: int = typer.Option(0, help="Max chorales to process (0 = all)."),
) -> None:
    """Extract ML feature dataset from all analyzed chorales in a corpus."""
    norm_dir = Path(f"data/normalized/{corpus}")
    derived_dir = Path(f"data/derived/{corpus}")

    graph_paths = sorted(norm_dir.glob("*.event_graph.json"))
    if not graph_paths:
        typer.echo(f"No event graphs found in {norm_dir}")
        raise typer.Exit(1)

    if limit > 0:
        graph_paths = graph_paths[:limit]

    rows: list[dict] = []
    note_sequences: list[dict] = []
    skipped = 0

    for gp in graph_paths:
        stem = gp.name.replace(".event_graph.json", "")
        bundle_path = derived_dir / f"{stem}.evidence_bundle.json"
        if not bundle_path.exists():
            skipped += 1
            continue

        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        graph = EventGraph.model_validate(json.loads(gp.read_text(encoding="utf-8")))

        features = extract_features(bundle, graph)
        rows.append(features)
        note_sequences.append(extract_note_sequences(graph))

    if not rows:
        typer.echo("No chorales with both event graph and evidence bundle found.")
        raise typer.Exit(1)

    if output is None:
        ext = {"csv": "csv", "json": "json", "huggingface": "hf"}.get(format, format)
        output = derived_dir / f"dataset.{ext}"

    if format == "csv":
        export_dataset_csv(rows, output)
    elif format == "json":
        export_dataset_json(rows, output)
    elif format == "huggingface":
        export_dataset_huggingface(rows, note_sequences, output)
    else:
        typer.echo(f"Unknown format: {format}. Use csv, json, or huggingface.")
        raise typer.Exit(1)

    typer.echo(f"Exported {len(rows)} chorales ({skipped} skipped) → {output}")


@app.command("midi")
def midi(
    score_path: Path = typer.Argument(..., help="MusicXML or event graph JSON path."),
    output: Path = typer.Option(None, "--output", "-o", help="Output MIDI path."),
    tempo: int = typer.Option(100, "--tempo", help="Tempo in BPM."),
    backend: str = typer.Option("native", "--backend", help="MIDI export backend: native, pymusica, or auto."),
    audio: str = typer.Option("", "--audio", help="Render to audio format (e.g., 'wav')."),
    soundfont: str = typer.Option("", "--soundfont", help="Path to .sf2 soundfont file."),
) -> None:
    """Export a chorale as MIDI (and optionally render to audio)."""
    from bachbot.exports.midi_export import midi_to_wav, write_midi

    if score_path.suffix == ".json":
        graph = EventGraph.model_validate(json.loads(score_path.read_text(encoding="utf-8")))
    else:
        graph = Normalizer().normalize(score_path)

    if output is None:
        output = score_path.with_suffix(".mid")

    write_midi(graph, output, tempo_bpm=tempo, backend=backend)
    typer.echo(f"MIDI: {output}")

    if audio:
        audio_path = output.with_suffix(f".{audio}")
        sf = soundfont or None
        from bachbot.exports.midi_export import midi_to_wav
        if midi_to_wav(output, audio_path, soundfont=sf):
            typer.echo(f"Audio: {audio_path}")
        else:
            typer.echo("Audio rendering skipped (FluidSynth not found or no soundfont).")
