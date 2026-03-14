from __future__ import annotations

import json
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bachbot.connectors.bach_digital import BachDigitalConnector
from bachbot.connectors.rism import RISMConnector
from bachbot.registry.catalog import CorpusCatalog
from bachbot.registry.checksums import sha256_file, sha256_text
from bachbot.registry.manifests import DatasetManifest
from bachbot.registry.storage import BachbotStorage

RECORD_METADATA_NAME = "record_metadata.json"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _write_json_value(payload: Any, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _ordered_unique_dicts(
    items: list[dict[str, Any]],
    *,
    unique_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    ordered: list[dict[str, Any]] = []
    for item in items:
        key = tuple(item.get(field) for field in unique_keys)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def _ensure_authority_manifest(manifest: DatasetManifest) -> None:
    if manifest.type != "authority_metadata":
        raise ValueError(f"Dataset {manifest.dataset_id} is not an authority dataset")


def _search_artifact_id(dataset_id: str, payload: dict[str, Any]) -> str:
    digest = sha256_text(json.dumps({"dataset_id": dataset_id, **payload}, sort_keys=True))
    return digest[:12]


def _collect_record_metadata_paths(raw_root: Path) -> list[Path]:
    return sorted(raw_root.rglob(RECORD_METADATA_NAME))


def _add_seed_origin(seed_origins: dict[tuple[str, str], list[str]], key: tuple[str, str], origin: str) -> None:
    seed_origins.setdefault(key, [])
    if origin not in seed_origins[key]:
        seed_origins[key].append(origin)


def sync_authority_dataset(
    dataset: str,
    *,
    manifest: DatasetManifest,
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
) -> dict[str, Any]:
    _ensure_authority_manifest(manifest)
    dataset_id = manifest.dataset_id
    catalog = catalog or CorpusCatalog()
    storage = BachbotStorage(dataset_id).ensure()
    raw_root = Path(storage.raw_dir)
    searches_root = raw_root / "searches"
    records_root = raw_root / "records"
    synced_at = _timestamp()

    if dataset_id == "bach_digital":
        connector = BachDigitalConnector()
        if kind is None:
            raise ValueError("Bach Digital sync requires an explicit kind")
        normalized_kind = connector.validate_kind(kind)
        primary_plan, search_records = _build_bach_digital_plan(
            connector=connector,
            dataset_id=dataset_id,
            kind=normalized_kind,
            record_ids=record_ids or [],
            record_urls=record_urls or [],
            query=query,
            query_field=query_field,
            limit=limit,
            searches_root=searches_root,
            synced_at=synced_at,
            catalog=catalog,
        )
        fetched_records = _fetch_bach_digital_records(
            connector=connector,
            manifest=manifest,
            catalog=catalog,
            records_root=records_root,
            primary_plan=primary_plan,
            include_linked=include_linked,
            synced_at=synced_at,
        )
    elif dataset_id == "rism":
        connector = RISMConnector()
        if mode is None:
            raise ValueError("RISM sync requires an explicit mode")
        normalized_mode = connector.validate_mode(mode)
        validated_rows = connector.validate_rows(rows or 20)
        primary_plan, search_records = _build_rism_plan(
            connector=connector,
            dataset_id=dataset_id,
            mode=normalized_mode,
            record_ids=record_ids or [],
            record_urls=record_urls or [],
            query=query,
            query_field=query_field,
            limit=limit,
            rows=validated_rows,
            searches_root=searches_root,
            synced_at=synced_at,
            catalog=catalog,
        )
        fetched_records = _fetch_rism_records(
            connector=connector,
            manifest=manifest,
            catalog=catalog,
            records_root=records_root,
            primary_plan=primary_plan,
            mode=normalized_mode,
            synced_at=synced_at,
        )
    else:
        raise ValueError(f"Unsupported authority dataset: {dataset_id}")

    inventory = {
        "dataset_id": dataset_id,
        "manifest_type": manifest.type,
        "raw_dir": storage.raw_dir,
        "synced_at": synced_at,
        "record_count": len(fetched_records),
        "primary_record_count": sum(1 for record in fetched_records if not record.get("linked_from")),
        "linked_record_count": sum(1 for record in fetched_records if record.get("linked_from")),
        "search_count": len(search_records),
        "records": fetched_records,
        "searches": search_records,
        "unit_label": "authority record(s)",
    }
    inventory_path = _write_json_value(inventory, raw_root / "sync_inventory.json")
    catalog.upsert_record(
        record_id=f"dataset_sync:{dataset_id}",
        record_type="dataset_sync",
        payload={**inventory, "inventory_path": str(inventory_path)},
    )
    return {**inventory, "inventory_path": str(inventory_path)}


def normalize_authority_dataset(
    dataset: str,
    *,
    manifest: DatasetManifest,
    catalog: CorpusCatalog | None = None,
) -> dict[str, Any]:
    _ensure_authority_manifest(manifest)
    dataset_id = manifest.dataset_id
    catalog = catalog or CorpusCatalog()
    storage = BachbotStorage(dataset_id).ensure()
    raw_root = Path(storage.raw_dir)
    normalized_root = Path(storage.normalized_dir)
    normalized_at = _timestamp()
    normalized_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    metadata_paths = _collect_record_metadata_paths(raw_root)
    if dataset_id == "bach_digital":
        connector = BachDigitalConnector()
        for metadata_path in metadata_paths:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            try:
                raw_paths = metadata["raw_paths"]
                structure_path = Path(raw_paths["structure_xml"])
                parsed = connector.parse_structure_xml(structure_path.read_text(encoding="utf-8"), kind=metadata["kind"])
                summary = _build_bach_digital_summary(
                    manifest=manifest,
                    metadata=metadata,
                    parsed=parsed,
                    normalized_at=normalized_at,
                )
                summary_path = normalized_root / f"{metadata['kind']}s" / f"{metadata['authority_id']}.summary.json"
                _write_json_value(summary, summary_path)
                record = {
                    **summary,
                    "summary_path": str(summary_path),
                    "summary_checksum": sha256_file(summary_path),
                    "normalized_at": normalized_at,
                }
                normalized_records.append(record)
                catalog.upsert_record(
                    record_id=f"normalized_authority:{dataset_id}:{metadata['kind']}:{metadata['authority_id']}",
                    record_type="normalized_authority",
                    payload=record,
                )
            except Exception as exc:
                failure = {
                    "dataset_id": dataset_id,
                    "metadata_path": str(metadata_path),
                    "error": str(exc),
                }
                failures.append(failure)
                catalog.upsert_record(
                    record_id=f"normalize_failure:{dataset_id}:{metadata.get('kind', 'unknown')}:{metadata.get('authority_id', metadata_path.stem)}",
                    record_type="normalize_failure",
                    payload=failure,
                )
    elif dataset_id == "rism":
        connector = RISMConnector()
        for metadata_path in metadata_paths:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            try:
                raw_paths = metadata["raw_paths"]
                resource_path = Path(raw_paths["resource_json"])
                parsed = connector.parse_source_payload(json.loads(resource_path.read_text(encoding="utf-8")))
                summary = _build_rism_summary(
                    manifest=manifest,
                    metadata=metadata,
                    parsed=parsed,
                    normalized_at=normalized_at,
                )
                summary_path = normalized_root / "sources" / f"{metadata['authority_id']}.summary.json"
                _write_json_value(summary, summary_path)
                record = {
                    **summary,
                    "summary_path": str(summary_path),
                    "summary_checksum": sha256_file(summary_path),
                    "normalized_at": normalized_at,
                }
                normalized_records.append(record)
                catalog.upsert_record(
                    record_id=f"normalized_authority:{dataset_id}:source:{metadata['authority_id']}",
                    record_type="normalized_authority",
                    payload=record,
                )
            except Exception as exc:
                failure = {
                    "dataset_id": dataset_id,
                    "metadata_path": str(metadata_path),
                    "error": str(exc),
                }
                failures.append(failure)
                catalog.upsert_record(
                    record_id=f"normalize_failure:{dataset_id}:source:{metadata.get('authority_id', metadata_path.stem)}",
                    record_type="normalize_failure",
                    payload=failure,
                )
    else:
        raise ValueError(f"Unsupported authority dataset: {dataset_id}")

    summary = {
        "dataset_id": dataset_id,
        "normalized_dir": storage.normalized_dir,
        "normalized_at": normalized_at,
        "normalized_count": len(normalized_records),
        "skipped_count": 0,
        "failure_count": len(failures),
        "normalized": normalized_records,
        "skipped": [],
        "failures": failures,
        "unit_label": "authority record(s)",
    }
    index_path = _write_json_value(summary, normalized_root / "normalization_index.json")
    catalog.upsert_record(
        record_id=f"dataset_normalization:{dataset_id}",
        record_type="dataset_normalization",
        payload={**summary, "index_path": str(index_path)},
    )
    return {**summary, "index_path": str(index_path)}


def analyze_authority_dataset(
    dataset: str,
    *,
    manifest: DatasetManifest,
    catalog: CorpusCatalog | None = None,
) -> dict[str, Any]:
    _ensure_authority_manifest(manifest)
    dataset_id = manifest.dataset_id
    catalog = catalog or CorpusCatalog()
    storage = BachbotStorage(dataset_id).ensure()
    normalized_root = Path(storage.normalized_dir)
    derived_root = Path(storage.derived_dir)
    analyzed_at = _timestamp()
    failure_records: list[dict[str, Any]] = []

    summary_paths = sorted(normalized_root.rglob("*.summary.json"))
    summary_payloads: list[dict[str, Any]] = []
    for path in summary_paths:
        try:
            summary_payloads.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            failure = {"dataset_id": dataset_id, "summary_path": str(path), "error": str(exc)}
            failure_records.append(failure)
            catalog.upsert_record(
                record_id=f"analysis_failure:{dataset_id}:{path.stem}",
                record_type="analysis_failure",
                payload=failure,
            )

    if dataset_id == "bach_digital":
        artifacts = _analyze_bach_digital(dataset_id=dataset_id, payloads=summary_payloads, derived_root=derived_root, analyzed_at=analyzed_at)
    elif dataset_id == "rism":
        artifacts = _analyze_rism(dataset_id=dataset_id, payloads=summary_payloads, derived_root=derived_root, analyzed_at=analyzed_at)
    else:
        raise ValueError(f"Unsupported authority dataset: {dataset_id}")

    summary = {
        "dataset_id": dataset_id,
        "derived_dir": storage.derived_dir,
        "analyzed_at": analyzed_at,
        "analysis_count": len(summary_payloads),
        "failure_count": len(failure_records),
        "analyses": artifacts,
        "failures": failure_records,
        "unit_label": "authority summary record(s)",
    }
    index_path = _write_json_value(summary, derived_root / "analysis_index.json")
    catalog.upsert_record(
        record_id=f"dataset_analysis:{dataset_id}",
        record_type="dataset_analysis",
        payload={**summary, "index_path": str(index_path)},
    )
    return {**summary, "index_path": str(index_path)}


def _build_bach_digital_plan(
    *,
    connector: BachDigitalConnector,
    dataset_id: str,
    kind: str,
    record_ids: list[str],
    record_urls: list[str],
    query: str | None,
    query_field: str | None,
    limit: int | None,
    searches_root: Path,
    synced_at: str,
    catalog: CorpusCatalog,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seed_origins: dict[tuple[str, str], list[str]] = {}
    primary_order: list[tuple[str, str]] = []
    for value in record_ids:
        canonical_id = connector.canonical_id(value, kind=kind)
        key = (kind, canonical_id)
        if key not in seed_origins:
            primary_order.append(key)
        _add_seed_origin(seed_origins, key, "record-id")
    for value in record_urls:
        canonical_id = connector.parse_record_url(value, kind=kind)
        key = (kind, canonical_id)
        if key not in seed_origins:
            primary_order.append(key)
        _add_seed_origin(seed_origins, key, "record-url")

    search_records: list[dict[str, Any]] = []
    if query is not None:
        search_payload = connector.search(kind=kind, query=query, query_field=query_field, rows=connector.default_search_rows)
        selected_ids = search_payload["record_ids"][:limit] if limit is not None else search_payload["record_ids"]
        artifact = {
            "dataset_id": dataset_id,
            "kind": kind,
            "query": query,
            "query_field": query_field,
            "limit": limit,
            "request_url": search_payload["request_url"],
            "request_params": search_payload["request_params"],
            "raw_record_ids": search_payload["raw_record_ids"],
            "selected_record_ids": selected_ids,
            "response_payload": search_payload["response_payload"],
            "synced_at": synced_at,
        }
        search_id = _search_artifact_id(dataset_id, artifact)
        artifact_path = _write_json_value(artifact, searches_root / f"{search_id}.json")
        record = {**artifact, "search_id": search_id, "artifact_path": str(artifact_path)}
        search_records.append(record)
        catalog.upsert_record(
            record_id=f"authority_search:{dataset_id}:{search_id}",
            record_type="authority_search",
            payload=record,
        )
        for canonical_id in selected_ids:
            key = (kind, canonical_id)
            if key not in seed_origins:
                primary_order.append(key)
            _add_seed_origin(seed_origins, key, f"search:{search_id}")

    primary_plan = [
        {"kind": record_kind, "authority_id": authority_id, "seed_origins": seed_origins[(record_kind, authority_id)]}
        for record_kind, authority_id in primary_order
    ]
    return primary_plan, search_records


def _build_rism_plan(
    *,
    connector: RISMConnector,
    dataset_id: str,
    mode: str,
    record_ids: list[str],
    record_urls: list[str],
    query: str | None,
    query_field: str | None,
    limit: int | None,
    rows: int,
    searches_root: Path,
    synced_at: str,
    catalog: CorpusCatalog,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seed_origins: dict[tuple[str, str], list[str]] = {}
    primary_order: list[tuple[str, str]] = []
    for value in record_ids:
        canonical_id = connector.canonical_id(value, mode=mode)
        key = ("source", canonical_id)
        if key not in seed_origins:
            primary_order.append(key)
        _add_seed_origin(seed_origins, key, "record-id")
    for value in record_urls:
        canonical_id = connector.parse_record_url(value, mode=mode)
        key = ("source", canonical_id)
        if key not in seed_origins:
            primary_order.append(key)
        _add_seed_origin(seed_origins, key, "record-url")

    search_records: list[dict[str, Any]] = []
    if query is not None:
        search_payload = connector.search(mode=mode, query=query, query_field=query_field, rows=rows)
        selected_ids = search_payload["record_ids"][:limit] if limit is not None else search_payload["record_ids"]
        artifact = {
            "dataset_id": dataset_id,
            "mode": mode,
            "query": query,
            "query_field": query_field,
            "rows": rows,
            "limit": limit,
            "request_url": search_payload["request_url"],
            "request_params": search_payload["request_params"],
            "raw_record_ids": search_payload["raw_record_ids"],
            "selected_record_ids": selected_ids,
            "response_payload": search_payload["response_payload"],
            "synced_at": synced_at,
        }
        search_id = _search_artifact_id(dataset_id, artifact)
        artifact_path = _write_json_value(artifact, searches_root / f"{search_id}.json")
        record = {**artifact, "search_id": search_id, "artifact_path": str(artifact_path)}
        search_records.append(record)
        catalog.upsert_record(
            record_id=f"authority_search:{dataset_id}:{search_id}",
            record_type="authority_search",
            payload=record,
        )
        for canonical_id in selected_ids:
            key = ("source", canonical_id)
            if key not in seed_origins:
                primary_order.append(key)
            _add_seed_origin(seed_origins, key, f"search:{search_id}")

    primary_plan = [
        {"kind": record_kind, "authority_id": authority_id, "seed_origins": seed_origins[(record_kind, authority_id)]}
        for record_kind, authority_id in primary_order
    ]
    return primary_plan, search_records


def _fetch_bach_digital_records(
    *,
    connector: BachDigitalConnector,
    manifest: DatasetManifest,
    catalog: CorpusCatalog,
    records_root: Path,
    primary_plan: list[dict[str, Any]],
    include_linked: bool,
    synced_at: str,
) -> list[dict[str, Any]]:
    queue: deque[dict[str, Any]] = deque(primary_plan)
    fetched: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    seed_origins: dict[tuple[str, str], list[str]] = {
        (item["kind"], item["authority_id"]): list(item["seed_origins"]) for item in primary_plan
    }

    while queue:
        item = queue.popleft()
        key = (item["kind"], item["authority_id"])
        if key in seen:
            continue
        seen.add(key)
        metadata = _sync_bach_digital_record(
            connector=connector,
            manifest=manifest,
            catalog=catalog,
            records_root=records_root,
            authority_id=item["authority_id"],
            kind=item["kind"],
            seed_origins=seed_origins[key],
            linked_from=item.get("linked_from"),
            synced_at=synced_at,
        )
        fetched.append(metadata)

        if not include_linked:
            continue
        if item.get("linked_from") is not None:
            continue
        if item["kind"] == "work":
            for linked_id in metadata.get("linked_source_ids", []):
                linked_key = ("source", linked_id)
                _add_seed_origin(seed_origins, linked_key, f"linked:{item['authority_id']}")
                queue.append(
                    {
                        "kind": "source",
                        "authority_id": linked_id,
                        "seed_origins": seed_origins[linked_key],
                        "linked_from": item["authority_id"],
                    }
                )
        else:
            for linked_id in metadata.get("linked_work_ids", []):
                linked_key = ("work", linked_id)
                _add_seed_origin(seed_origins, linked_key, f"linked:{item['authority_id']}")
                queue.append(
                    {
                        "kind": "work",
                        "authority_id": linked_id,
                        "seed_origins": seed_origins[linked_key],
                        "linked_from": item["authority_id"],
                    }
                )

    return fetched


def _fetch_rism_records(
    *,
    connector: RISMConnector,
    manifest: DatasetManifest,
    catalog: CorpusCatalog,
    records_root: Path,
    primary_plan: list[dict[str, Any]],
    mode: str,
    synced_at: str,
) -> list[dict[str, Any]]:
    fetched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in primary_plan:
        authority_id = item["authority_id"]
        if authority_id in seen:
            continue
        seen.add(authority_id)
        fetched.append(
            _sync_rism_record(
                connector=connector,
                manifest=manifest,
                catalog=catalog,
                records_root=records_root,
                authority_id=authority_id,
                mode=mode,
                seed_origins=item["seed_origins"],
                synced_at=synced_at,
            )
        )
    return fetched


def _sync_bach_digital_record(
    *,
    connector: BachDigitalConnector,
    manifest: DatasetManifest,
    catalog: CorpusCatalog,
    records_root: Path,
    authority_id: str,
    kind: str,
    seed_origins: list[str],
    linked_from: str | None,
    synced_at: str,
) -> dict[str, Any]:
    structure = connector.fetch_structure_xml(authority_id)
    jsonld = connector.fetch_jsonld_payload(authority_id)
    parsed = connector.parse_structure_xml(structure["text"], kind=kind)
    linked_lookup_path: Path | None = None
    linked_source_ids: list[str] = []
    linked_work_ids: list[str] = parsed.get("linked_work_ids", [])

    record_dir = records_root / kind / authority_id
    structure_path = record_dir / "structure.xml"
    structure_path.parent.mkdir(parents=True, exist_ok=True)
    structure_path.write_text(structure["text"], encoding="utf-8")
    jsonld_path = _write_json_value(jsonld["payload"], record_dir / "jsonld.json")

    if kind == "work":
        linked_lookup = connector.linked_source_ids(authority_id)
        linked_source_ids = linked_lookup["record_ids"]
        linked_lookup_record = {
            "request_url": linked_lookup["request_url"],
            "request_params": linked_lookup["request_params"],
            "raw_record_ids": linked_lookup["raw_record_ids"],
            "selected_record_ids": linked_lookup["record_ids"],
            "response_payload": linked_lookup["response_payload"],
        }
        linked_lookup_path = _write_json_value(linked_lookup_record, record_dir / "linked_sources.json")

    raw_paths = {
        "structure_xml": str(structure_path),
        "jsonld": str(jsonld_path),
    }
    raw_checksums = {
        "structure_xml": sha256_file(structure_path),
        "jsonld": sha256_file(jsonld_path),
    }
    if linked_lookup_path is not None:
        raw_paths["linked_sources"] = str(linked_lookup_path)
        raw_checksums["linked_sources"] = sha256_file(linked_lookup_path)

    metadata_path = record_dir / RECORD_METADATA_NAME
    metadata = {
        "dataset_id": manifest.dataset_id,
        "kind": kind,
        "authority_id": authority_id,
        "title": parsed.get("title"),
        "persistent_url": connector.persistent_url(authority_id),
        "export_urls": {
            "persistent": connector.persistent_url(authority_id),
            "structure_xml": structure["url"],
            "jsonld": jsonld["url"],
        },
        "raw_paths": raw_paths,
        "raw_checksums": raw_checksums,
        "checksum_policy": manifest.checksum_policy,
        "synced_at": synced_at,
        "seed_origins": seed_origins,
        "linked_from": linked_from,
        "linked_source_ids": linked_source_ids,
        "linked_work_ids": linked_work_ids,
        "created_at": parsed.get("created_at"),
        "modified_at": parsed.get("modified_at"),
        "metadata_path": str(metadata_path),
    }
    _write_json_value(metadata, metadata_path)
    catalog.upsert_record(
        record_id=f"raw_authority_record:{manifest.dataset_id}:{kind}:{authority_id}",
        record_type="raw_authority_record",
        payload=metadata,
    )
    return metadata


def _sync_rism_record(
    *,
    connector: RISMConnector,
    manifest: DatasetManifest,
    catalog: CorpusCatalog,
    records_root: Path,
    authority_id: str,
    mode: str,
    seed_origins: list[str],
    synced_at: str,
) -> dict[str, Any]:
    resource = connector.fetch_resource_jsonld(authority_id, mode=mode)
    parsed = connector.parse_source_payload(resource["payload"])
    marcxml = connector.fetch_marcxml(authority_id, mode=mode)

    record_dir = records_root / "source" / authority_id
    resource_path = _write_json_value(resource["payload"], record_dir / "resource.json")
    raw_paths = {"resource_json": str(resource_path)}
    raw_checksums = {"resource_json": sha256_file(resource_path)}

    if marcxml["available"]:
        marcxml_path = record_dir / "marcxml.xml"
        marcxml_path.write_text(marcxml["text"], encoding="utf-8")
        raw_paths["marcxml"] = str(marcxml_path)
        raw_checksums["marcxml"] = sha256_file(marcxml_path)
    else:
        marc_status_path = _write_json_value(
            {
                "available": False,
                "status_code": marcxml["status_code"],
                "url": marcxml["url"],
            },
            record_dir / "marcxml_status.json",
        )
        raw_paths["marcxml_status"] = str(marc_status_path)
        raw_checksums["marcxml_status"] = sha256_file(marc_status_path)

    metadata_path = record_dir / RECORD_METADATA_NAME
    metadata = {
        "dataset_id": manifest.dataset_id,
        "kind": "source",
        "mode": mode,
        "authority_id": authority_id,
        "title": parsed.get("title"),
        "persistent_url": connector.record_url(authority_id, mode=mode),
        "export_urls": {
            "jsonld": resource["url"],
            "marcxml": marcxml["url"],
        },
        "raw_paths": raw_paths,
        "raw_checksums": raw_checksums,
        "checksum_policy": manifest.checksum_policy,
        "synced_at": synced_at,
        "seed_origins": seed_origins,
        "created_at": parsed.get("created_at"),
        "modified_at": parsed.get("modified_at"),
        "metadata_path": str(metadata_path),
    }
    _write_json_value(metadata, metadata_path)
    catalog.upsert_record(
        record_id=f"raw_authority_record:{manifest.dataset_id}:source:{authority_id}",
        record_type="raw_authority_record",
        payload=metadata,
    )
    return metadata


def _build_bach_digital_summary(
    *,
    manifest: DatasetManifest,
    metadata: dict[str, Any],
    parsed: dict[str, Any],
    normalized_at: str,
) -> dict[str, Any]:
    external_refs = _ordered_unique_dicts(
        parsed.get("external_refs", []),
        unique_keys=("source", "value", "url"),
    )
    return {
        "dataset_id": manifest.dataset_id,
        "kind": metadata["kind"],
        "authority_id": metadata["authority_id"],
        "title": parsed.get("title"),
        "titles": parsed.get("titles", {}),
        "repository": parsed.get("repository"),
        "shelfmark": parsed.get("shelfmark"),
        "date_statements": parsed.get("date_statements", []),
        "catalog_identifiers": parsed.get("catalog_identifiers", []),
        "external_refs": external_refs,
        "linked_source_ids": metadata.get("linked_source_ids", []),
        "linked_work_ids": parsed.get("linked_work_ids", []),
        "export_urls": metadata["export_urls"],
        "license": parsed.get("license"),
        "provenance": {
            "retrieved_at": metadata["synced_at"],
            "normalized_at": normalized_at,
            "seed_origins": metadata["seed_origins"],
            "linked_from": metadata.get("linked_from"),
            "source_url": metadata["persistent_url"],
            "created_at": metadata.get("created_at"),
            "modified_at": metadata.get("modified_at"),
            "raw_artifacts": metadata["raw_paths"],
        },
        "checksums": metadata["raw_checksums"],
        "checksum_policy": manifest.checksum_policy,
    }


def _build_rism_summary(
    *,
    manifest: DatasetManifest,
    metadata: dict[str, Any],
    parsed: dict[str, Any],
    normalized_at: str,
) -> dict[str, Any]:
    return {
        "dataset_id": manifest.dataset_id,
        "kind": "source",
        "authority_id": metadata["authority_id"],
        "title": parsed.get("title"),
        "titles": parsed.get("titles", {}),
        "standardized_title": parsed.get("standardized_title"),
        "repository": parsed.get("repository"),
        "shelfmark": parsed.get("shelfmark"),
        "date_statements": parsed.get("date_statements", []),
        "catalog_identifiers": parsed.get("catalog_identifiers", []),
        "external_refs": parsed.get("external_refs", []),
        "external_resources": parsed.get("external_resources", []),
        "relationships": parsed.get("relationships", []),
        "exemplars": parsed.get("exemplars", []),
        "source_item_ids": parsed.get("source_item_ids", []),
        "holding_institution_ids": parsed.get("holding_institution_ids", []),
        "export_urls": metadata["export_urls"],
        "provenance": {
            "retrieved_at": metadata["synced_at"],
            "normalized_at": normalized_at,
            "seed_origins": metadata["seed_origins"],
            "source_url": metadata["persistent_url"],
            "created_at": metadata.get("created_at"),
            "modified_at": metadata.get("modified_at"),
            "raw_artifacts": metadata["raw_paths"],
        },
        "checksums": metadata["raw_checksums"],
        "checksum_policy": manifest.checksum_policy,
    }


def _analyze_bach_digital(
    *,
    dataset_id: str,
    payloads: list[dict[str, Any]],
    derived_root: Path,
    analyzed_at: str,
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for payload in payloads:
        if payload["kind"] == "work":
            for source_id in payload.get("linked_source_ids", []):
                edges.append(
                    {
                        "work_id": payload["authority_id"],
                        "source_id": source_id,
                        "relationship": "has_source",
                    }
                )
        elif payload["kind"] == "source":
            for work_id in payload.get("linked_work_ids", []):
                edges.append(
                    {
                        "work_id": work_id,
                        "source_id": payload["authority_id"],
                        "relationship": "has_source",
                    }
                )
    edges = _ordered_unique_dicts(edges, unique_keys=("work_id", "source_id", "relationship"))

    external_refs: list[dict[str, Any]] = []
    for payload in payloads:
        for reference in payload.get("external_refs", []):
            external_refs.append(
                {
                    "authority_id": payload["authority_id"],
                    "kind": payload["kind"],
                    "source": reference.get("source"),
                    "value": reference.get("value"),
                    "url": reference.get("url"),
                }
            )
    external_refs = _ordered_unique_dicts(external_refs, unique_keys=("authority_id", "source", "value", "url"))

    edge_payload = {
        "dataset_id": dataset_id,
        "generated_at": analyzed_at,
        "edge_count": len(edges),
        "edges": edges,
    }
    edge_path = _write_json_value(edge_payload, derived_root / "work_source_edges.json")
    external_ref_payload = {
        "dataset_id": dataset_id,
        "generated_at": analyzed_at,
        "external_ref_count": len(external_refs),
        "external_refs": external_refs,
    }
    external_ref_path = _write_json_value(external_ref_payload, derived_root / "external_ref_index.json")

    return [
        {
            "artifact_type": "work_source_edges",
            "path": str(edge_path),
            "count": len(edges),
        },
        {
            "artifact_type": "external_ref_index",
            "path": str(external_ref_path),
            "count": len(external_refs),
        },
    ]


def _analyze_rism(
    *,
    dataset_id: str,
    payloads: list[dict[str, Any]],
    derived_root: Path,
    analyzed_at: str,
) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    for payload in payloads:
        source_id = payload["authority_id"]
        for relationship in payload.get("relationships", []):
            relationships.append(
                {
                    "source_id": source_id,
                    "relationship": relationship.get("role"),
                    "relationship_label": relationship.get("role_label"),
                    "qualifier": relationship.get("qualifier"),
                    "target_id": relationship.get("target_id"),
                    "target_type": relationship.get("target_type"),
                    "target_label": relationship.get("target_label"),
                }
            )
        for exemplar in payload.get("exemplars", []):
            if exemplar.get("institution_id") is None:
                continue
            relationships.append(
                {
                    "source_id": source_id,
                    "relationship": "held_by",
                    "relationship_label": "Held by",
                    "qualifier": None,
                    "target_id": exemplar.get("institution_id"),
                    "target_type": "rism:Institution",
                    "target_label": exemplar.get("institution_label"),
                }
            )
        for item_id in payload.get("source_item_ids", []):
            relationships.append(
                {
                    "source_id": source_id,
                    "relationship": "contains_item",
                    "relationship_label": "Contains item",
                    "qualifier": None,
                    "target_id": f"https://rism.online/sources/{item_id}",
                    "target_type": "rism:Source",
                    "target_label": item_id,
                }
            )
    relationships = _ordered_unique_dicts(
        relationships,
        unique_keys=("source_id", "relationship", "target_id", "qualifier"),
    )

    external_resources: list[dict[str, Any]] = []
    for payload in payloads:
        for resource in payload.get("external_resources", []):
            external_resources.append(
                {
                    "source_id": payload["authority_id"],
                    "url": resource.get("url"),
                    "label": resource.get("label"),
                    "resource_type": resource.get("resource_type"),
                    "context": resource.get("context"),
                }
            )
    external_resources = _ordered_unique_dicts(
        external_resources,
        unique_keys=("source_id", "url", "context"),
    )

    relationship_payload = {
        "dataset_id": dataset_id,
        "generated_at": analyzed_at,
        "relationship_count": len(relationships),
        "relationships": relationships,
    }
    relationship_path = _write_json_value(relationship_payload, derived_root / "relationship_index.json")
    external_resource_payload = {
        "dataset_id": dataset_id,
        "generated_at": analyzed_at,
        "external_resource_count": len(external_resources),
        "external_resources": external_resources,
    }
    external_resource_path = _write_json_value(external_resource_payload, derived_root / "external_resource_index.json")

    return [
        {
            "artifact_type": "relationship_index",
            "path": str(relationship_path),
            "count": len(relationships),
        },
        {
            "artifact_type": "external_resource_index",
            "path": str(external_resource_path),
            "count": len(external_resources),
        },
    ]
