from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from bachbot.analysis import analyze_graph
from bachbot.claims import build_evidence_bundle
from bachbot.connectors.local_files import LocalFilesConnector
from bachbot.encodings import EventGraph, Normalizer, build_measure_map
from bachbot.exports import export_json, export_report
from bachbot.registry.authority import (
    analyze_authority_dataset as _analyze_authority_dataset,
    normalize_authority_dataset as _normalize_authority_dataset,
    sync_authority_dataset as _sync_authority_dataset,
)
from bachbot.registry.catalog import CorpusCatalog
from bachbot.registry.checksums import sha256_file
from bachbot.registry.manifests import DatasetManifest
from bachbot.registry.storage import BachbotStorage

SUPPORTED_SYMBOLIC_SUFFIXES = {".musicxml", ".xml", ".mei", ".krn", ".mscx", ".tsv"}
SUPPORTED_NORMALIZATION_SUFFIXES = {".musicxml", ".xml", ".tsv"}


def canonical_dataset_id(dataset: str) -> str:
    aliases = {
        "bach-digital": "bach_digital",
        "dcml": "dcml_bach_chorales",
    }
    return aliases.get(dataset.lower(), dataset)


def load_registered_manifest(dataset: str, catalog: CorpusCatalog | None = None) -> DatasetManifest:
    dataset_id = canonical_dataset_id(dataset)
    catalog = catalog or CorpusCatalog()
    manifest = catalog.get_dataset(dataset_id)
    if manifest is None:
        raise KeyError(dataset_id)
    return manifest


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _artifact_stem(relative_path: Path) -> str:
    label = relative_path.as_posix()
    for suffix in reversed(relative_path.suffixes):
        if label.endswith(suffix):
            label = label[: -len(suffix)]
    return label.replace("/", "__")


def _write_summary(path: Path, payload: dict) -> Path:
    export_json(payload, path)
    return path


def sync_open_corpus_dataset(dataset: str, source_root: str | Path, catalog: CorpusCatalog | None = None) -> dict:
    manifest = load_registered_manifest(dataset, catalog=catalog)
    dataset_id = manifest.dataset_id
    catalog = catalog or CorpusCatalog()
    storage = BachbotStorage(dataset_id).ensure()
    source_root = Path(source_root).expanduser().resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise FileNotFoundError(source_root)

    synced_at = _timestamp()
    raw_root = Path(storage.raw_dir)
    assets: list[dict] = []
    files = sorted(path for path in source_root.rglob("*") if path.is_file())
    for source_path in files:
        relative_path = source_path.relative_to(source_root)
        destination = raw_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        checksum = sha256_file(destination)
        suffix = source_path.suffix.lower()
        asset = {
            "dataset_id": dataset_id,
            "source_root": str(source_root),
            "source_path": str(source_path),
            "source_relpath": relative_path.as_posix(),
            "raw_path": str(destination),
            "checksum": checksum,
            "checksum_policy": manifest.checksum_policy,
            "synced_at": synced_at,
            "size_bytes": destination.stat().st_size,
            "suffix": suffix,
            "symbolic": suffix in SUPPORTED_SYMBOLIC_SUFFIXES,
            "normalization_supported": suffix in SUPPORTED_NORMALIZATION_SUFFIXES,
        }
        assets.append(asset)
        catalog.upsert_record(
            record_id=f"raw_asset:{dataset_id}:{relative_path.as_posix()}",
            record_type="raw_asset",
            payload=asset,
        )

    inventory = {
        "dataset_id": dataset_id,
        "manifest_type": manifest.type,
        "source_root": str(source_root),
        "raw_dir": storage.raw_dir,
        "synced_at": synced_at,
        "checksum_policy": manifest.checksum_policy,
        "asset_count": len(assets),
        "symbolic_count": sum(1 for asset in assets if asset["symbolic"]),
        "normalizable_count": sum(1 for asset in assets if asset["normalization_supported"]),
        "assets": assets,
    }
    inventory_path = _write_summary(raw_root / "sync_inventory.json", inventory)
    catalog.upsert_record(
        record_id=f"dataset_sync:{dataset_id}",
        record_type="dataset_sync",
        payload={**inventory, "inventory_path": str(inventory_path)},
    )
    return {**inventory, "inventory_path": str(inventory_path), "record_count": len(assets), "unit_label": "asset(s)"}


def sync_authority_dataset(
    dataset: str,
    *,
    record_ids: list[str] | None = None,
    record_urls: list[str] | None = None,
    query: str | None = None,
    query_field: str | None = None,
    kind: str | None = None,
    mode: str | None = None,
    limit: int | None = None,
    rows: int | None = None,
    include_linked: bool = False,
    catalog: CorpusCatalog | None = None,
) -> dict:
    catalog = catalog or CorpusCatalog()
    manifest = load_registered_manifest(dataset, catalog=catalog)
    return _sync_authority_dataset(
        dataset,
        manifest=manifest,
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


def normalize_corpus_dataset(dataset: str, catalog: CorpusCatalog | None = None) -> dict:
    manifest = load_registered_manifest(dataset, catalog=catalog)
    if manifest.type == "authority_metadata":
        return _normalize_authority_dataset(dataset, manifest=manifest, catalog=catalog)
    dataset_id = manifest.dataset_id
    catalog = catalog or CorpusCatalog()
    storage = BachbotStorage(dataset_id).ensure()
    raw_root = Path(storage.raw_dir)
    normalized_root = Path(storage.normalized_dir)
    connector = LocalFilesConnector()
    normalizer = Normalizer()
    normalized: list[dict] = []
    skipped: list[dict] = []
    failures: list[dict] = []
    normalized_at = _timestamp()

    for raw_path in connector.discover(raw_root):
        relative_path = raw_path.relative_to(raw_root)
        suffix = raw_path.suffix.lower()
        artifact_stem = _artifact_stem(relative_path)
        is_notes_tsv = suffix == ".tsv" and raw_path.name.endswith(".notes.tsv")
        if suffix not in SUPPORTED_NORMALIZATION_SUFFIXES or (suffix == ".tsv" and not is_notes_tsv):
            skipped_record = {
                "dataset_id": dataset_id,
                "raw_path": str(raw_path),
                "source_relpath": relative_path.as_posix(),
                "suffix": suffix,
                "reason": "unsupported_normalization_format",
            }
            skipped.append(skipped_record)
            catalog.upsert_record(
                record_id=f"normalize_skip:{dataset_id}:{relative_path.as_posix()}",
                record_type="normalize_skip",
                payload=skipped_record,
            )
            continue
        try:
            graph = normalizer.normalize(raw_path, work_id=artifact_stem, encoding_id=artifact_stem)
        except Exception as exc:
            failure = {
                "dataset_id": dataset_id,
                "raw_path": str(raw_path),
                "source_relpath": relative_path.as_posix(),
                "suffix": suffix,
                "error": str(exc),
            }
            failures.append(failure)
            catalog.upsert_record(
                record_id=f"normalize_failure:{dataset_id}:{relative_path.as_posix()}",
                record_type="normalize_failure",
                payload=failure,
            )
            continue

        graph.metadata.provenance.extend(
            [
                f"Dataset manifest: {dataset_id}",
                f"Raw checksum ({manifest.checksum_policy}): {sha256_file(raw_path)}",
                f"Batch normalized at {normalized_at}",
            ]
        )
        measure_map = [measure.model_dump(mode="json") for measure in build_measure_map(graph)]
        graph_path = normalized_root / f"{artifact_stem}.event_graph.json"
        measure_map_path = normalized_root / f"{artifact_stem}.measure_map.json"
        export_json(graph.model_dump(mode="json"), graph_path)
        export_json(
            {
                "dataset_id": dataset_id,
                "work_id": graph.work_id,
                "encoding_id": graph.metadata.encoding_id,
                "source_relpath": relative_path.as_posix(),
                "measures": measure_map,
            },
            measure_map_path,
        )
        record = {
            "dataset_id": dataset_id,
            "work_id": graph.work_id,
            "encoding_id": graph.metadata.encoding_id,
            "title": graph.title,
            "source_relpath": relative_path.as_posix(),
            "raw_path": str(raw_path),
            "event_graph_path": str(graph_path),
            "measure_map_path": str(measure_map_path),
            "normalized_at": normalized_at,
            "event_graph_checksum": sha256_file(graph_path),
            "measure_map_checksum": sha256_file(measure_map_path),
        }
        normalized.append(record)
        catalog.upsert_record(
            record_id=f"normalized_work:{dataset_id}:{artifact_stem}",
            record_type="normalized_work",
            payload=record,
        )

    summary = {
        "dataset_id": dataset_id,
        "normalized_dir": storage.normalized_dir,
        "normalized_at": normalized_at,
        "normalized_count": len(normalized),
        "skipped_count": len(skipped),
        "failure_count": len(failures),
        "normalized": normalized,
        "skipped": skipped,
        "failures": failures,
    }
    index_path = _write_summary(normalized_root / "normalization_index.json", summary)
    catalog.upsert_record(
        record_id=f"dataset_normalization:{dataset_id}",
        record_type="dataset_normalization",
        payload={**summary, "index_path": str(index_path)},
    )
    return {**summary, "index_path": str(index_path), "unit_label": "work(s)"}


def analyze_corpus_dataset(dataset: str, catalog: CorpusCatalog | None = None) -> dict:
    manifest = load_registered_manifest(dataset, catalog=catalog)
    if manifest.type == "authority_metadata":
        return _analyze_authority_dataset(dataset, manifest=manifest, catalog=catalog)
    dataset_id = manifest.dataset_id
    catalog = catalog or CorpusCatalog()
    storage = BachbotStorage(dataset_id).ensure()
    normalized_root = Path(storage.normalized_dir)
    derived_root = Path(storage.derived_dir)
    analyses: list[dict] = []
    failures: list[dict] = []
    analyzed_at = _timestamp()

    for event_graph_path in sorted(normalized_root.glob("*.event_graph.json")):
        artifact_stem = event_graph_path.name[: -len(".event_graph.json")]
        try:
            payload = json.loads(event_graph_path.read_text(encoding="utf-8"))
            graph = EventGraph.model_validate(payload)
            analysis = analyze_graph(graph)
            bundle = build_evidence_bundle(graph, analysis)
        except Exception as exc:
            failure = {
                "dataset_id": dataset_id,
                "event_graph_path": str(event_graph_path),
                "error": str(exc),
            }
            failures.append(failure)
            catalog.upsert_record(
                record_id=f"analysis_failure:{dataset_id}:{artifact_stem}",
                record_type="analysis_failure",
                payload=failure,
            )
            continue

        analysis_path = derived_root / f"{artifact_stem}.analysis.json"
        bundle_path = derived_root / f"{artifact_stem}.evidence_bundle.json"
        report_path = derived_root / f"{artifact_stem}.report.md"
        export_json(analysis.model_dump(mode="json"), analysis_path)
        export_json(bundle.model_dump(mode="json"), bundle_path)
        export_report(bundle, report_path)
        record = {
            "dataset_id": dataset_id,
            "work_id": graph.work_id,
            "encoding_id": graph.metadata.encoding_id,
            "analysis_path": str(analysis_path),
            "bundle_path": str(bundle_path),
            "report_path": str(report_path),
            "analyzed_at": analyzed_at,
            "analysis_checksum": sha256_file(analysis_path),
            "bundle_checksum": sha256_file(bundle_path),
            "report_checksum": sha256_file(report_path),
            "cadence_count": len(analysis.cadences),
            "harmonic_event_count": len(analysis.harmonic_events),
        }
        analyses.append(record)
        catalog.upsert_record(
            record_id=f"derived_analysis:{dataset_id}:{artifact_stem}",
            record_type="derived_analysis",
            payload=record,
        )

    summary = {
        "dataset_id": dataset_id,
        "derived_dir": storage.derived_dir,
        "analyzed_at": analyzed_at,
        "analysis_count": len(analyses),
        "failure_count": len(failures),
        "analyses": analyses,
        "failures": failures,
    }
    index_path = _write_summary(derived_root / "analysis_index.json", summary)
    catalog.upsert_record(
        record_id=f"dataset_analysis:{dataset_id}",
        record_type="dataset_analysis",
        payload={**summary, "index_path": str(index_path)},
    )
    return {**summary, "index_path": str(index_path), "unit_label": "normalized work(s)"}
