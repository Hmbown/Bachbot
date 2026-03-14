"""Analysis CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from bachbot.analysis import analyze_graph
from bachbot.analysis.annotations import bundle_to_annotation_layer, compare_annotation_layers, load_annotation_layer, load_dcml_annotation_layer
from bachbot.analysis.stats.embeddings import analyze_dataset_embeddings
from bachbot.claims import build_evidence_bundle
from bachbot.cli.io import emit_json
from bachbot.encodings import Normalizer

app = typer.Typer(help="Deterministic analysis commands.")


@app.command("chorale")
def analyze_chorale(
    score_path: Path,
    work_id: str | None = None,
    output: Path | None = typer.Option(None, "--output", help="Write the evidence bundle JSON to a file instead of stdout."),
) -> None:
    """Analyze a chorale score into a deterministic evidence bundle."""

    graph = Normalizer().normalize(score_path, work_id=work_id)
    analysis = analyze_graph(graph)
    bundle = build_evidence_bundle(graph, analysis)
    emit_json(bundle.model_dump(mode="json"), output=output)


@app.command("compare")
def compare_annotations(
    target: Path,
    source: list[str] = typer.Option(..., "--source", help="Two sources to compare. Use 'bachbot' or a JSON file path."),
    summary_only: bool = typer.Option(False, "--summary-only", help="Emit only the derived diff summary JSON."),
    output: Path | None = typer.Option(None, "--output", help="Write the annotation diff JSON to a file instead of stdout."),
) -> None:
    """Compare Bachbot findings against a local annotation source."""

    if len(source) != 2:
        raise typer.BadParameter("Provide exactly two --source values.", param_hint="--source")
    left = _resolve_annotation_source(target, source[0])
    right = _resolve_annotation_source(target, source[1])
    diff = compare_annotation_layers(left, right)
    payload = diff.summary.model_dump(mode="json") if summary_only else diff.model_dump(mode="json")
    emit_json(payload, output=output)


@app.command("annotate")
def export_annotation_layer(
    target: Path,
    output: Path | None = typer.Option(None, "--output", help="Write the normalized annotation layer JSON to a file instead of stdout."),
) -> None:
    """Normalize a score or bundle JSON into an annotation layer."""

    layer = _load_annotation_target(target)
    emit_json(layer.model_dump(mode="json"), output=output)


@app.command("embeddings")
def analyze_embeddings(
    dataset: str = typer.Option("dcml_bach_chorales", "--dataset", help="Corpus dataset under data/derived/."),
    dimension: int = typer.Option(32, "--dimension", min=2, help="Chord embedding dimensionality."),
    context_window: int = typer.Option(2, "--context-window", min=1, help="Neighbor window for chord co-occurrences."),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Directory for JSON, numpy, and plot artifacts."),
    visualize: bool = typer.Option(False, "--visualize", help="Render a 2D UMAP scatter plot for chorale embeddings."),
    collapse_repeats: bool = typer.Option(
        True,
        "--collapse-repeats/--keep-repeats",
        help="Collapse repeated adjacent harmony labels before training.",
    ),
) -> None:
    """Train corpus-wide chord and chorale embeddings from deterministic harmony."""

    manifest = analyze_dataset_embeddings(
        dataset=dataset,
        dimension=dimension,
        context_window=context_window,
        output_dir=output_dir,
        visualize=visualize,
        collapse_repeats=collapse_repeats,
    )
    emit_json(
        {
            "dataset_id": manifest.dataset_id,
            "dimension": manifest.dimension,
            "context_window": manifest.context_window,
            "corpus_size": manifest.corpus_size,
            "chord_type_count": manifest.chord_type_count,
            "projection_method": manifest.projection_method,
            "diagnostics": manifest.diagnostics.model_dump(mode="json"),
            "manifest_path": manifest.manifest_path,
            "chord_vectors_path": manifest.chord_vectors_path,
            "chorale_vectors_path": manifest.chorale_vectors_path,
            "chorale_projection_path": manifest.chorale_projection_path,
            "chord_labels_path": manifest.chord_labels_path,
            "chorale_metadata_path": manifest.chorale_metadata_path,
            "visualization_path": manifest.visualization_path,
        }
    )


def _resolve_annotation_source(target: Path, source: str):
    if source == "bachbot":
        return _load_annotation_target(target)
    if source == "dcml":
        graph = Normalizer().normalize(target)
        work_id = graph.work_id
        try:
            return load_dcml_annotation_layer(work_id)
        except FileNotFoundError as exc:
            raise typer.BadParameter(str(exc), param_hint="--source") from exc
    source_path = Path(source)
    if not source_path.exists():
        raise typer.BadParameter(f"Annotation source not found: {source_path}", param_hint="--source")
    try:
        return load_annotation_layer(source_path)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--source") from exc


@app.command("fugue")
def analyze_fugue_cmd(
    score_path: Path,
    work_id: str | None = None,
    output: Path | None = typer.Option(None, "--output", help="Write the fugue analysis JSON to a file instead of stdout."),
) -> None:
    """Analyze a fugue score: subject, answer, entries, stretto, episodes."""
    from bachbot.analysis.fugue.pipeline import analyze_fugue

    graph = Normalizer().normalize(score_path, work_id=work_id)
    report = analyze_fugue(graph)
    emit_json(report.model_dump(mode="json"), output=output)


@app.command("style")
def compare_styles(
    left: str = typer.Argument(..., help="Work ID or evidence bundle path"),
    right: str = typer.Argument(..., help="Work ID or evidence bundle path"),
    dataset: str = typer.Option("dcml_bach_chorales", "--dataset", help="Corpus dataset under data/derived/."),
    output: Path | None = typer.Option(None, "--output", help="Write comparison JSON to a file instead of stdout."),
) -> None:
    """Compare style fingerprints of two chorales."""
    from bachbot.analysis.style import _load_bundle, compare_fingerprints, compute_style_fingerprint

    bundle_a = _load_bundle(left, dataset=dataset)
    bundle_b = _load_bundle(right, dataset=dataset)
    fp_a = compute_style_fingerprint(bundle_a)
    fp_b = compute_style_fingerprint(bundle_b)
    comparison = compare_fingerprints(fp_a, fp_b)
    emit_json(comparison.model_dump(mode="json"), output=output)


@app.command("anomaly")
def detect_anomaly(
    target: str = typer.Argument(..., help="Work ID or evidence bundle path"),
    dataset: str = typer.Option("dcml_bach_chorales", "--dataset"),
    limit: int = typer.Option(50, "--limit", help="Max corpus chorales to compare against"),
    output: Path | None = typer.Option(None, "--output", help="Write anomaly report JSON to a file instead of stdout."),
) -> None:
    """Detect stylistic anomalies in a chorale."""
    from bachbot.analysis.style import (
        _load_bundle,
        compute_anomaly,
        compute_style_fingerprint,
        load_corpus_fingerprints,
    )

    bundle = _load_bundle(target, dataset=dataset)
    target_fp = compute_style_fingerprint(bundle)
    corpus_fps = load_corpus_fingerprints(dataset, limit=limit)
    report = compute_anomaly(target_fp, corpus_fps)
    emit_json(report.model_dump(mode="json"), output=output)


def _load_annotation_target(target: Path):
    if target.suffix.lower() == ".json":
        try:
            return load_annotation_layer(target)
        except ValueError as exc:
            raise typer.BadParameter(str(exc), param_hint="target") from exc
    graph = Normalizer().normalize(target)
    analysis = analyze_graph(graph)
    bundle = build_evidence_bundle(graph, analysis)
    return bundle_to_annotation_layer(bundle)
