"""Composition CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from bachbot.composition import compose_chorale_study
from bachbot.encodings import Normalizer
from bachbot.exports import export_json, export_musicxml

app = typer.Typer(help="Constraint-first composition commands.")


@app.command("melody")
def compose_melody(
    chords: str = typer.Option("I IV V I", "--chords", help="Space-separated roman numerals."),
    key: str = typer.Option("C", "--key", help="Tonic pitch name."),
    mode: str = typer.Option("major", "--mode", help="major or minor."),
    meter: str = typer.Option("4/4", "--meter", help="Time signature."),
    beats_per_chord: float = typer.Option(1.0, "--beats-per-chord", help="Duration per chord in quarter notes."),
    from_bundle: Path | None = typer.Option(None, "--from-bundle", help="Path to evidence bundle JSON."),
    seed: int = typer.Option(42, "--seed", help="Random seed for deterministic output."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output path for JSON."),
) -> None:
    """Generate a soprano melody from a harmonic plan."""
    from bachbot.composition.generators.melody import (
        MelodyConfig,
        generate_melody,
        plan_from_bundle,
        plan_from_chord_sequence,
    )

    cfg = MelodyConfig(seed=seed)

    if from_bundle is not None:
        plan = plan_from_bundle(from_bundle)
        typer.echo(f"Loaded plan from bundle: {from_bundle} ({len(plan)} events)")
    else:
        chord_list = chords.strip().split()
        plan = plan_from_chord_sequence(chord_list, key=key, mode=mode, meter=meter, beats_per_chord=beats_per_chord)
        typer.echo(f"Plan: {' '.join(chord_list)} in {key} {mode}")

    melody = generate_melody(plan, config=cfg)
    result = [note.model_dump(mode="json", exclude_none=True) for note in melody]

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        typer.echo(f"Melody written to: {output}")
    else:
        typer.echo(json.dumps(result, indent=2))


@app.command("chorale")
def compose_chorale(
    score_path: Path,
    output_prefix: Path = typer.Option(
        Path("data/derived/chorale-study"),
        "--output-prefix",
        help="Prefix for MusicXML, artifact, and report outputs; existing files at those paths will be overwritten.",
    ),
    evidence_bundle: Path | None = typer.Option(
        None,
        "--evidence-bundle",
        help="Path to an evidence bundle JSON to guide chord selection and cadence placement.",
    ),
    musicxml_backend: str = typer.Option(
        "native",
        "--musicxml-backend",
        help="MusicXML export backend: native, pymusica, or auto.",
    ),
) -> None:
    """Generate a labeled chorale study from a single-line cantus input."""

    graph = Normalizer().normalize(score_path)
    bundle = None
    if evidence_bundle is not None:
        bundle = json.loads(evidence_bundle.read_text(encoding="utf-8"))
        typer.echo(f"Loaded evidence bundle: {evidence_bundle}")
    study_graph, artifact, report = compose_chorale_study(graph, bundle=bundle)
    musicxml_path = output_prefix.with_suffix(".musicxml")
    artifact_path = output_prefix.with_suffix(".artifact.json")
    report_path = output_prefix.with_suffix(".report.json")
    export_musicxml(study_graph, musicxml_path, backend=musicxml_backend)
    export_json(artifact.model_dump(mode="json"), artifact_path)
    export_json(report, report_path)
    typer.echo(f"MusicXML: {musicxml_path}")
    typer.echo(f"Artifact: {artifact_path}")
    typer.echo(f"Report: {report_path}")


@app.command("from-bass")
def compose_from_bass(
    bass_input: Path = typer.Argument(..., help="MusicXML file with a single-voice bass line."),
    figures: str = typer.Option("", "--figures", help="Space-separated figured bass symbols; use '-' for root position."),
    key: str = typer.Option("C", "--key", help="Key tonic (e.g., C, G, Bb)."),
    mode: str = typer.Option("major", "--mode", help="major or minor."),
    meter: str = typer.Option("4/4", "--meter", help="Time signature."),
    output_prefix: Path = typer.Option(
        Path("data/derived/figured-bass-realization"),
        "--output-prefix",
        help="Prefix for output MusicXML.",
    ),
    musicxml_backend: str = typer.Option(
        "native",
        "--musicxml-backend",
        help="MusicXML export backend: native, pymusica, or auto.",
    ),
) -> None:
    """Realize a figured bass line into SATB voices."""
    from bachbot.composition.generators.figured_bass import realize_figured_bass

    graph = Normalizer().normalize(bass_input)
    voice_id = graph.ordered_voice_ids()[0]
    bass_notes = [n for n in graph.notes_by_voice()[voice_id] if n.midi is not None and not n.is_rest]

    if figures.strip():
        fig_list = figures.strip().split()
    else:
        fig_list = [""] * len(bass_notes)

    if len(fig_list) != len(bass_notes):
        typer.echo(f"Error: {len(fig_list)} figures but {len(bass_notes)} bass notes.", err=True)
        raise typer.Exit(code=1)

    result_graph = realize_figured_bass(
        bass_notes, fig_list, key_tonic=key, mode=mode, meter=meter,
    )
    musicxml_path = output_prefix.with_suffix(".musicxml")
    export_musicxml(result_graph, musicxml_path, backend=musicxml_backend)
    typer.echo(f"MusicXML: {musicxml_path}")


@app.command("invention")
def compose_invention(
    subject: str = typer.Option("C4 D4 E4 F4 G4 A4 G4 F4", "--subject", help="Space-separated pitch names (e.g., 'C4 D4 E4 F4')."),
    subject_file: Path | None = typer.Option(None, "--subject-file", help="MusicXML file with a single-voice subject."),
    key: str = typer.Option("C", "--key", help="Key tonic (e.g., C, G, Bb)."),
    mode: str = typer.Option("major", "--mode", help="major or minor."),
    meter: str = typer.Option("4/4", "--meter", help="Time signature."),
    seed: int = typer.Option(42, "--seed", help="Random seed for deterministic output."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output path for MusicXML."),
    musicxml_backend: str = typer.Option(
        "native",
        "--musicxml-backend",
        help="MusicXML export backend: native, pymusica, or auto.",
    ),
) -> None:
    """Generate a two-part invention from a subject."""
    from bachbot.composition.generators.invention import (
        InventionConfig,
        generate_invention,
        parse_subject_string,
    )

    if subject_file is not None:
        graph = Normalizer().normalize(subject_file)
        voice_id = graph.ordered_voice_ids()[0]
        subject_notes = [n for n in graph.notes_by_voice()[voice_id] if n.midi is not None and not n.is_rest]
        typer.echo(f"Loaded subject from {subject_file}: {len(subject_notes)} notes")
    else:
        subject_notes = parse_subject_string(subject)
        typer.echo(f"Subject: {subject}")

    cfg = InventionConfig(key_tonic=key, mode=mode, meter=meter, seed=seed)
    invention_graph = generate_invention(subject_notes, config=cfg)

    summary = {
        "key": key,
        "mode": mode,
        "meter": meter,
        "measures": invention_graph.measure_numbers(),
        "voices": invention_graph.ordered_voice_ids(),
        "total_notes": len([n for n in invention_graph.notes if not n.is_rest]),
    }
    typer.echo(json.dumps(summary, indent=2))

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        export_musicxml(invention_graph, output, backend=musicxml_backend)
        typer.echo(f"MusicXML: {output}")


@app.command("counterpoint")
def compose_counterpoint(
    species: int = typer.Option(1, "--species", help="Species number (1-5)."),
    cantus: str = typer.Option("Fux-1", "--cantus", help="Name from built-in cantus firmi, or space/comma-separated MIDI notes."),
    position: str = typer.Option("above", "--position", help="'above' or 'below' the cantus firmus."),
    seed: int = typer.Option(42, "--seed", help="Random seed for deterministic output."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output path for JSON."),
) -> None:
    """Generate and validate a species counterpoint exercise."""
    from bachbot.composition.counterpoint import (
        CantusFirmus,
        generate_counterpoint,
        get_cantus_firmus,
        validate_counterpoint,
    )

    # Parse cantus: try name lookup first, then parse as MIDI notes
    try:
        cf = get_cantus_firmus(cantus)
    except ValueError:
        # Parse as space or comma separated MIDI notes
        raw = cantus.replace(",", " ").split()
        try:
            midi_notes = [int(x) for x in raw]
        except ValueError:
            typer.echo(f"Error: '{cantus}' is not a known cantus firmus name or valid MIDI note list.", err=True)
            raise typer.Exit(code=1)
        cf = CantusFirmus(name="custom", midi_notes=midi_notes)

    notes = generate_counterpoint(cf, species=species, position=position, seed=seed)
    cp_midi = [n.midi for n in notes]

    report = validate_counterpoint(cf.midi_notes, cp_midi, species=species, position=position)

    result = {
        "species": species,
        "cantus": cf.model_dump(mode="json"),
        "counterpoint": cp_midi,
        "counterpoint_notes": [n.model_dump(mode="json", exclude_none=True) for n in notes],
        "validation": report.model_dump(mode="json"),
    }

    text = json.dumps(result, indent=2)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        typer.echo(f"Written to: {output}")
    else:
        typer.echo(text)
