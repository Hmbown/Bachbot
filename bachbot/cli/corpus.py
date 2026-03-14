from __future__ import annotations

from pathlib import Path

import typer

from bachbot.analysis.stats.patterns import filter_patterns, mine_dataset_patterns
from bachbot.cli.io import emit_json
from bachbot.encodings import Normalizer
from bachbot.encodings.alignment import align_editions
from bachbot.registry.catalog import CorpusCatalog
from bachbot.registry.manifests import dump_manifest, load_manifest
from bachbot.registry.batch import (
    batch_sync_bach_digital,
    batch_sync_rism_linked,
    build_corpus_coverage_report,
)
from bachbot.registry.workflows import (
    analyze_corpus_dataset,
    canonical_dataset_id,
    load_registered_manifest,
    normalize_corpus_dataset,
    sync_authority_dataset,
    sync_open_corpus_dataset,
)

app = typer.Typer(help="Corpus manifests, registry, and remote metadata sync.")


def _print_pattern_table(rows: list, *, top: int) -> None:
    typer.echo("pattern\tcount\tworks\tsupport\tpmi\tsignificant")
    for summary in rows[:top]:
        typer.echo(
            f"{summary.pattern}\t{summary.count}\t{summary.work_count}\t"
            f"{summary.support:.4f}\t{summary.pmi:.4f}\t{summary.significant}"
        )


def _print_pattern_occurrences(summary, *, top: int) -> None:
    typer.echo(f"Pattern: {summary.pattern}")
    typer.echo(
        f"Count: {summary.count} | Works: {summary.work_count} | "
        f"Support: {summary.support:.4f} | PMI: {summary.pmi:.4f} | Significant: {summary.significant}"
    )
    typer.echo("work_id\tmeasures\tonsets\trefs\tglobal_key\tlocal_keys")
    for occurrence in summary.occurrences[:top]:
        typer.echo(
            f"{occurrence.work_id}\tm{occurrence.start_measure}-m{occurrence.end_measure}\t"
            f"{occurrence.start_onset:.2f}-{occurrence.end_onset:.2f}\t"
            f"{occurrence.start_ref_id}->{occurrence.end_ref_id}\t"
            f"{occurrence.global_key or ''}\t"
            f"{', '.join(occurrence.local_keys)}"
        )


@app.command("diff")
def diff_editions(
    left_score: Path,
    right_score: Path,
    edition_a: str = typer.Option("left", "--edition-a", help="Label for the left edition in the diff output."),
    edition_b: str = typer.Option("right", "--edition-b", help="Label for the right edition in the diff output."),
    output: Path | None = typer.Option(None, "--output", help="Write the variant report JSON to a file instead of stdout."),
) -> None:
    """Diff two score files using stable measure/onset/voice note addresses."""

    normalizer = Normalizer()
    left_graph = normalizer.normalize(left_score)
    right_graph = normalizer.normalize(right_score)
    report = align_editions(left_graph, right_graph, left_label=edition_a, right_label=edition_b)
    emit_json(report.model_dump(mode="json"), output=output)


@app.command("register")
def register_manifest(manifest_path: Path) -> None:
    manifest = load_manifest(manifest_path)
    catalog = CorpusCatalog()
    catalog.register_manifest(manifest)
    typer.echo(f"Registered dataset manifest: {manifest.dataset_id}")


@app.command("list")
def list_manifests() -> None:
    catalog = CorpusCatalog()
    for manifest in catalog.list_datasets():
        typer.echo(f"{manifest.dataset_id}\t{manifest.type}\t{manifest.source_url}")


@app.command("sync")
def sync_dataset(
    dataset: str,
    source_root: Path | None = typer.Option(None, "--source-root", file_okay=False, dir_okay=True, resolve_path=True),
    record_id: list[str] | None = typer.Option(None, "--record-id"),
    record_url: list[str] | None = typer.Option(None, "--record-url"),
    query: str | None = typer.Option(None, "--query"),
    query_field: str | None = typer.Option(None, "--query-field"),
    kind: str | None = typer.Option(None, "--kind"),
    mode: str | None = typer.Option(None, "--mode"),
    limit: int | None = typer.Option(None, "--limit", min=1),
    rows: int | None = typer.Option(None, "--rows"),
    include_linked: bool = typer.Option(False, "--include-linked/--no-include-linked"),
) -> None:
    dataset_id = canonical_dataset_id(dataset)
    record_ids = list(record_id or [])
    record_urls = list(record_url or [])
    catalog = CorpusCatalog()
    try:
        manifest = load_registered_manifest(dataset_id, catalog=catalog)
    except KeyError as exc:
        raise typer.BadParameter(f"Dataset is not registered: {exc.args[0]}") from exc
    if manifest.type == "authority_metadata":
        if source_root is not None:
            raise typer.BadParameter("--source-root is only supported for local corpus sync")
        if query_field is not None and query is None:
            raise typer.BadParameter("--query-field requires --query")
        if not record_ids and not record_urls and query is None:
            raise typer.BadParameter("Authority sync requires --record-id, --record-url, or --query")
        if dataset_id == "bach_digital":
            if kind is None:
                raise typer.BadParameter("--kind work|source is required for bach_digital sync")
            if mode is not None:
                raise typer.BadParameter("--mode is not supported for bach_digital sync")
            if rows is not None:
                raise typer.BadParameter("--rows is only supported for rism search sync")
        elif dataset_id == "rism":
            if mode is None:
                raise typer.BadParameter("--mode sources is required for rism sync")
            if mode != "sources":
                raise typer.BadParameter("RISM sync currently supports only --mode sources")
            if kind is not None:
                raise typer.BadParameter("--kind is not supported for rism sync")
            if include_linked:
                raise typer.BadParameter("--include-linked is only supported for bach_digital sync")
            if rows is not None and rows not in {20, 40, 100}:
                raise typer.BadParameter("--rows must be one of 20, 40, or 100")
            if rows is not None and query is None:
                raise typer.BadParameter("--rows requires --query")
        elif rows is not None:
            raise typer.BadParameter("--rows is only supported for rism search sync")
        try:
            summary = sync_authority_dataset(
                dataset_id,
                record_ids=record_ids,
                record_urls=record_urls,
                query=query,
                query_field=query_field,
                kind=kind,
                mode=mode,
                limit=limit,
                rows=rows,
                include_linked=include_linked,
                catalog=catalog,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        if source_root is None:
            raise typer.BadParameter(f"--source-root is required for {dataset_id} sync")
        if record_ids or record_urls or query is not None or query_field is not None or kind is not None or mode is not None:
            raise typer.BadParameter("Remote authority sync options are not supported for local corpus datasets")
        if limit is not None or rows is not None or include_linked:
            raise typer.BadParameter("Authority-only sync options are not supported for local corpus datasets")
        summary = sync_open_corpus_dataset(dataset_id, source_root, catalog=catalog)
    typer.echo(f"Synced {summary['record_count']} {summary['unit_label']} for {summary['dataset_id']}")
    typer.echo(f"Inventory: {summary['inventory_path']}")


@app.command("normalize")
def normalize_dataset(dataset: str) -> None:
    try:
        summary = normalize_corpus_dataset(dataset)
    except KeyError as exc:
        raise typer.BadParameter(f"Dataset is not registered: {exc.args[0]}") from exc
    typer.echo(
        f"Normalized {summary['normalized_count']} {summary.get('unit_label', 'record(s)')} "
        f"with {summary['skipped_count']} skipped and {summary['failure_count']} failure(s)"
    )
    typer.echo(f"Index: {summary['index_path']}")


@app.command("analyze")
def analyze_dataset(dataset: str) -> None:
    try:
        summary = analyze_corpus_dataset(dataset)
    except KeyError as exc:
        raise typer.BadParameter(f"Dataset is not registered: {exc.args[0]}") from exc
    typer.echo(
        f"Analyzed {summary['analysis_count']} {summary.get('unit_label', 'record(s)')} "
        f"with {summary['failure_count']} failure(s)"
    )
    typer.echo(f"Index: {summary['index_path']}")


@app.command("patterns")
def corpus_patterns(
    dataset: str = typer.Option("dcml_bach_chorales", "--dataset"),
    ngram: int = typer.Option(4, "--ngram", min=2),
    top: int = typer.Option(20, "--top", min=1),
    pattern: str | None = typer.Option(None, "--pattern"),
    mode: str | None = typer.Option(None, "--mode"),
    significant_only: bool = typer.Option(False, "--significant-only/--all-patterns"),
    output: Path | None = typer.Option(None, "--output", dir_okay=False, resolve_path=True),
    min_count: int = typer.Option(4, "--min-count", min=1),
    min_work_count: int = typer.Option(4, "--min-work-count", min=1),
    min_pmi: float = typer.Option(0.5, "--min-pmi"),
    null_trials: int = typer.Option(32, "--null-trials", min=1),
) -> None:
    try:
        index, output_path = mine_dataset_patterns(
            dataset=dataset,
            ngram=ngram,
            mode=mode,
            output=output,
            min_count=min_count,
            min_work_count=min_work_count,
            min_pmi=min_pmi,
            null_trials=null_trials,
        )
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc

    rows = filter_patterns(index, pattern=pattern, significant_only=significant_only)
    if not rows:
        typer.echo("No patterns matched the requested filters.")
        typer.echo(f"Index: {output_path}")
        return

    if pattern is None:
        _print_pattern_table(rows, top=top)
    else:
        _print_pattern_occurrences(rows[0], top=top)
    typer.echo(f"Index: {output_path}")


@app.command("batch-sync")
def batch_sync(
    dataset: str,
    include_linked: bool = typer.Option(False, "--include-linked/--no-include-linked"),
    delay: float = typer.Option(1.0, "--delay", min=0.0),
    dry_run: bool = typer.Option(False, "--dry-run/--no-dry-run"),
    source_root: Path | None = typer.Option(None, "--source-root", file_okay=False, dir_okay=True, resolve_path=True),
) -> None:
    """Batch-sync an entire dataset (enumerate + fetch all records)."""
    dataset_id = canonical_dataset_id(dataset)
    catalog = CorpusCatalog()
    try:
        manifest = load_registered_manifest(dataset_id, catalog=catalog)
    except KeyError as exc:
        raise typer.BadParameter(f"Dataset is not registered: {exc.args[0]}") from exc

    if dataset_id == "bach_digital":
        summary = batch_sync_bach_digital(
            include_linked=include_linked,
            delay=delay,
            dry_run=dry_run,
            catalog=catalog,
        )
        typer.echo(
            f"Bach Digital: {summary['total_works_found']} works found, "
            f"{summary['already_synced']} already synced, "
            f"{summary['synced']} newly synced"
            f"{' (dry-run)' if dry_run else ''}"
        )
    elif dataset_id == "rism":
        summary = batch_sync_rism_linked(delay=delay, catalog=catalog)
        typer.echo(f"RISM: {summary['linked_rism_ids_found']} linked IDs found, {summary['synced']} synced")
    elif manifest.type != "authority_metadata":
        if source_root is None:
            raise typer.BadParameter(f"--source-root is required for {dataset_id} batch-sync")
        summary = sync_open_corpus_dataset(dataset_id, source_root, catalog=catalog)
        typer.echo(f"Synced {summary['record_count']} {summary['unit_label']} for {dataset_id}")
    else:
        raise typer.BadParameter(f"Batch sync not supported for dataset type: {manifest.type}")


@app.command("coverage")
def coverage() -> None:
    """Generate and display a corpus coverage report."""
    report = build_corpus_coverage_report()
    for dataset_id, entry in report.get("datasets", {}).items():
        typer.echo(
            f"{dataset_id}: synced={entry['synced']} normalized={entry['normalized']} analyzed={entry['analyzed']}"
        )
    if report.get("report_path"):
        typer.echo(f"Report: {report['report_path']}")


@app.command("pipeline")
def pipeline(
    dataset: str,
    source_root: Path | None = typer.Option(None, "--source-root", file_okay=False, dir_okay=True, resolve_path=True),
) -> None:
    """Run register + sync + normalize + analyze in sequence for a dataset."""
    dataset_id = canonical_dataset_id(dataset)
    catalog = CorpusCatalog()
    try:
        manifest = load_registered_manifest(dataset_id, catalog=catalog)
    except KeyError as exc:
        raise typer.BadParameter(f"Dataset is not registered: {exc.args[0]}") from exc

    if manifest.type == "authority_metadata":
        typer.echo("Pipeline for authority datasets: use batch-sync + normalize + analyze individually")
        return

    if source_root is None:
        raise typer.BadParameter(f"--source-root is required for {dataset_id} pipeline")
    sync_summary = sync_open_corpus_dataset(dataset_id, source_root, catalog=catalog)
    typer.echo(f"Synced {sync_summary['record_count']} {sync_summary['unit_label']}")

    norm_summary = normalize_corpus_dataset(dataset_id, catalog=catalog)
    typer.echo(
        f"Normalized {norm_summary['normalized_count']} with "
        f"{norm_summary['skipped_count']} skipped, {norm_summary['failure_count']} failures"
    )

    analysis_summary = analyze_corpus_dataset(dataset_id, catalog=catalog)
    typer.echo(
        f"Analyzed {analysis_summary['analysis_count']} with {analysis_summary['failure_count']} failures"
    )


@app.command("dump-manifest")
def dump_manifest_command(manifest_path: Path, output: Path) -> None:
    manifest = load_manifest(manifest_path)
    dump_manifest(manifest, output)
    typer.echo(f"Wrote manifest copy to {output}")
