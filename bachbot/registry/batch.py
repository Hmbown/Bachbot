"""Batch enumeration, sync, and coverage reporting for corpus ingest."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bachbot.connectors.bach_digital import BachDigitalConnector
from bachbot.registry.authority import RECORD_METADATA_NAME
from bachbot.registry.catalog import CorpusCatalog
from bachbot.registry.storage import BachbotStorage
from bachbot.registry.workflows import (
    canonical_dataset_id,
    load_registered_manifest,
    sync_authority_dataset,
    sync_open_corpus_dataset,
)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(payload: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def enumerate_bach_digital_works(
    connector: BachDigitalConnector | None = None,
    *,
    rows_per_page: int = 100,
    delay: float = 1.0,
) -> list[str]:
    connector = connector or BachDigitalConnector()
    all_ids: list[str] = []
    seen: set[str] = set()
    start = 0
    num_found: int | None = None

    while True:
        result = connector.search(kind="work", query="*:*", rows=rows_per_page, start=start)
        if num_found is None:
            num_found = result["num_found"]
        for record_id in result["record_ids"]:
            if record_id not in seen:
                seen.add(record_id)
                all_ids.append(record_id)
        start += rows_per_page
        if start >= num_found:
            break
        time.sleep(delay)

    return all_ids


def batch_sync_bach_digital(
    *,
    include_linked: bool = False,
    delay: float = 1.0,
    dry_run: bool = False,
    rows_per_page: int = 100,
    catalog: CorpusCatalog | None = None,
    connector: BachDigitalConnector | None = None,
) -> dict[str, Any]:
    catalog = catalog or CorpusCatalog()
    connector = connector or BachDigitalConnector()
    manifest = load_registered_manifest("bach_digital", catalog=catalog)
    storage = BachbotStorage("bach_digital").ensure()
    records_root = Path(storage.raw_dir) / "records"

    work_ids = enumerate_bach_digital_works(connector, rows_per_page=rows_per_page, delay=delay)

    existing: set[str] = set()
    if records_root.exists():
        for metadata_path in records_root.rglob(RECORD_METADATA_NAME):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                existing.add(metadata["authority_id"])
            except Exception:
                pass

    to_sync = [wid for wid in work_ids if wid not in existing]
    skipped = [wid for wid in work_ids if wid in existing]

    summary = {
        "dataset_id": "bach_digital",
        "total_works_found": len(work_ids),
        "already_synced": len(skipped),
        "to_sync": len(to_sync),
        "synced": 0,
        "dry_run": dry_run,
        "include_linked": include_linked,
    }

    if dry_run:
        summary["work_ids"] = work_ids
        summary["skipped_ids"] = skipped
        summary["to_sync_ids"] = to_sync
        progress_path = _write_json(summary, Path(storage.raw_dir) / "batch_progress.json")
        summary["progress_path"] = str(progress_path)
        return summary

    synced_count = 0
    failures: list[dict[str, str]] = []
    for work_id in to_sync:
        try:
            sync_authority_dataset(
                "bach_digital",
                record_ids=[work_id],
                kind="work",
                include_linked=include_linked,
                catalog=catalog,
            )
            synced_count += 1
        except Exception as exc:
            failures.append({"work_id": work_id, "error": str(exc)})
        summary["synced"] = synced_count
        summary["failures"] = failures
        _write_json(summary, Path(storage.raw_dir) / "batch_progress.json")
        if delay > 0 and work_id != to_sync[-1]:
            time.sleep(delay)

    summary["synced"] = synced_count
    progress_path = _write_json(summary, Path(storage.raw_dir) / "batch_progress.json")
    summary["progress_path"] = str(progress_path)
    return summary


def batch_sync_rism_linked(
    *,
    delay: float = 1.0,
    catalog: CorpusCatalog | None = None,
) -> dict[str, Any]:
    catalog = catalog or CorpusCatalog()
    storage = BachbotStorage("bach_digital").ensure()
    normalized_root = Path(storage.normalized_dir)

    rism_ids: list[str] = []
    seen: set[str] = set()
    sources_dir = normalized_root / "sources"
    if sources_dir.exists():
        for summary_path in sorted(sources_dir.glob("*.summary.json")):
            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
                for ref in payload.get("external_refs", []):
                    if ref.get("source") == "rism" and ref.get("value"):
                        rid = ref["value"]
                        if rid not in seen:
                            seen.add(rid)
                            rism_ids.append(rid)
            except Exception:
                pass

    works_dir = normalized_root / "works"
    if works_dir.exists():
        for summary_path in sorted(works_dir.glob("*.summary.json")):
            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
                for ref in payload.get("external_refs", []):
                    if ref.get("source") == "rism" and ref.get("value"):
                        rid = ref["value"]
                        if rid not in seen:
                            seen.add(rid)
                            rism_ids.append(rid)
            except Exception:
                pass

    summary: dict[str, Any] = {
        "dataset_id": "rism",
        "linked_rism_ids_found": len(rism_ids),
        "synced": 0,
    }

    if not rism_ids:
        return summary

    failures: list[dict[str, str]] = []
    for i, rism_id in enumerate(rism_ids):
        try:
            sync_authority_dataset(
                "rism",
                record_ids=[rism_id],
                mode="sources",
                catalog=catalog,
            )
            summary["synced"] = i + 1
        except Exception as exc:
            failures.append({"rism_id": rism_id, "error": str(exc)})
        summary["failures"] = failures
        if delay > 0 and i < len(rism_ids) - 1:
            time.sleep(delay)

    return summary


def build_corpus_coverage_report(catalog: CorpusCatalog | None = None) -> dict[str, Any]:
    catalog = catalog or CorpusCatalog()
    datasets = {}

    for dataset_id in ("bach_digital", "rism", "dcml_bach_chorales"):
        try:
            storage = BachbotStorage(dataset_id).ensure()
        except Exception:
            continue

        raw_root = Path(storage.raw_dir)
        normalized_root = Path(storage.normalized_dir)
        derived_root = Path(storage.derived_dir)

        sync_inv_path = raw_root / "sync_inventory.json"
        norm_idx_path = normalized_root / "normalization_index.json"
        analysis_idx_path = derived_root / "analysis_index.json"

        entry: dict[str, Any] = {"dataset_id": dataset_id, "synced": 0, "normalized": 0, "analyzed": 0}

        if sync_inv_path.exists():
            inv = json.loads(sync_inv_path.read_text(encoding="utf-8"))
            if inv.get("manifest_type") == "authority_metadata":
                # Count actual record directories for authority datasets
                records_dir = raw_root / "records"
                entry["synced"] = len(list(records_dir.rglob(RECORD_METADATA_NAME))) if records_dir.exists() else 0
            else:
                entry["synced"] = inv.get("record_count", inv.get("asset_count", 0))

        if norm_idx_path.exists():
            idx = json.loads(norm_idx_path.read_text(encoding="utf-8"))
            entry["normalized"] = idx.get("normalized_count", 0)

        if analysis_idx_path.exists():
            idx = json.loads(analysis_idx_path.read_text(encoding="utf-8"))
            entry["analyzed"] = idx.get("analysis_count", 0)

        datasets[dataset_id] = entry

    report = {
        "generated_at": _timestamp(),
        "datasets": datasets,
    }

    for dataset_id in ("bach_digital", "rism", "dcml_bach_chorales"):
        try:
            storage = BachbotStorage(dataset_id).ensure()
            report_path = _write_json(report, Path(storage.derived_dir).parent / "corpus_coverage.json")
            report["report_path"] = str(report_path)
            break
        except Exception:
            pass

    return report
