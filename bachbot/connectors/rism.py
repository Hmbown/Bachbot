"""RISM connector."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

from bachbot.registry.manifests import DatasetManifest


def _ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _select_multilingual_text(
    mapping: dict[str, list[str]] | dict[str, Any] | None,
    preferred: tuple[str, ...] = ("en", "none", "de"),
) -> str | None:
    if not isinstance(mapping, dict):
        return None
    normalized: dict[str, list[str]] = {}
    for key, value in mapping.items():
        if isinstance(value, list):
            normalized[key] = [str(item) for item in value if str(item).strip()]
        elif value is not None:
            normalized[key] = [str(value)]
    for language in preferred:
        values = normalized.get(language, [])
        if values:
            return values[0]
    for values in normalized.values():
        if values:
            return values[0]
    return None


class RISMConnector:
    """Client for RISM authority data."""

    base_url = "https://rism.online"
    allowed_rows = {20, 40, 100}
    timeout = 20.0

    def build_manifest(self, retrieved_at: str) -> DatasetManifest:
        return DatasetManifest(
            dataset_id="rism",
            type="authority_metadata",
            source_url=self.base_url,
            retrieved_at=retrieved_at,
            license={
                "data": "CC BY 4.0",
                "site_content": "CC BY 4.0",
            },
            notes=[
                "Prefer persistent record identifiers.",
                "Store record provenance separately from local encodings.",
            ],
        )

    def validate_mode(self, mode: str) -> str:
        normalized = mode.strip().lower()
        if normalized != "sources":
            raise ValueError(f"Unsupported RISM mode: {mode}")
        return normalized

    def validate_rows(self, rows: int) -> int:
        if rows not in self.allowed_rows:
            raise ValueError(f"Unsupported RISM rows value: {rows}")
        return rows

    def canonical_id(self, value: str, *, mode: str = "sources") -> str:
        self.validate_mode(mode)
        candidate = value.strip()
        if candidate.startswith("http://") or candidate.startswith("https://"):
            return self.parse_record_url(candidate, mode=mode)
        if candidate.startswith("sources/"):
            candidate = candidate.split("/", 1)[1]
        if re.fullmatch(r"\d+", candidate) is None:
            raise ValueError(f"Could not parse RISM source identifier: {value}")
        return candidate

    def parse_record_url(self, url: str, *, mode: str = "sources") -> str:
        self.validate_mode(mode)
        parsed = urlparse(url)
        match = re.search(r"/sources/(\d+)", parsed.path)
        if match is None:
            raise ValueError(f"Could not parse RISM source URL: {url}")
        return match.group(1)

    def record_url(self, record_id: str, *, mode: str = "sources") -> str:
        canonical_id = self.canonical_id(record_id, mode=mode)
        return f"{self.base_url}/sources/{canonical_id}"

    def search(
        self,
        *,
        mode: str = "sources",
        query: str,
        query_field: str | None = None,
        rows: int = 20,
    ) -> dict[str, Any]:
        normalized_mode = self.validate_mode(mode)
        validated_rows = self.validate_rows(rows)
        params: dict[str, Any] = {"mode": normalized_mode, "rows": str(validated_rows)}
        if query_field is None:
            params["q"] = query
        else:
            params["fq"] = f"{query_field}:{query}"
        response = httpx.get(
            f"{self.base_url}/search",
            params=params,
            headers={"Accept": "application/ld+json, application/json;q=0.9, text/html;q=0.1"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = self._decode_search_payload(response.text)
        raw_record_ids = [
            self.canonical_id(item["id"], mode=normalized_mode)
            for item in payload.get("items", [])
            if item.get("id")
        ]
        return {
            "request_url": str(response.url),
            "request_params": params,
            "response_payload": payload,
            "raw_record_ids": raw_record_ids,
            "record_ids": _ordered_unique(raw_record_ids),
        }

    def fetch_resource_jsonld(self, record_id: str, *, mode: str = "sources") -> dict[str, Any]:
        url = self.record_url(record_id, mode=mode)
        response = httpx.get(
            url,
            headers={"Accept": "application/ld+json, application/json;q=0.9"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return {"url": str(response.url), "payload": json.loads(response.text)}

    def fetch_marcxml(self, record_id: str, *, mode: str = "sources") -> dict[str, Any]:
        url = self.record_url(record_id, mode=mode)
        response = httpx.get(
            url,
            headers={"Accept": "application/marcxml+xml"},
            timeout=self.timeout,
        )
        if response.status_code == 406:
            return {
                "url": str(response.url),
                "available": False,
                "status_code": 406,
                "text": None,
            }
        response.raise_for_status()
        return {
            "url": str(response.url),
            "available": True,
            "status_code": response.status_code,
            "text": response.text,
        }

    def parse_source_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        canonical_id = self.canonical_id(payload["id"], mode="sources")
        summary_entries = payload.get("contents", {}).get("summary", [])
        title = _select_multilingual_text(payload.get("label")) or canonical_id
        standardized_title = None
        date_statements: list[dict[str, Any]] = []
        for entry in summary_entries:
            label = self._entry_label(entry)
            if label in {"Standardized title", "Uniform title"}:
                standardized_title = self._entry_value(entry)
            if label in {"Dates", "Date"}:
                date_statements.append(
                    {
                        "label": label,
                        "value": self._entry_value(entry),
                    }
                )

        external_resources = self._collect_external_resources(payload)
        external_refs = [
            {
                "source": "rism",
                "value": f"sources/{canonical_id}",
                "url": self.record_url(canonical_id, mode="sources"),
            }
        ]
        for resource in external_resources:
            url = resource["url"]
            bach_digital_ref = self._bach_digital_ref(url)
            if bach_digital_ref is not None:
                external_refs.append({"source": "bach_digital", "value": bach_digital_ref, "url": url})
            else:
                external_refs.append(
                    {
                        "source": resource.get("resource_type") or "external_resource",
                        "value": url,
                        "url": url,
                    }
                )

        exemplars = self._parse_exemplars(payload.get("exemplars", {}).get("items", []))
        relationships = self._parse_relationships(payload.get("relationships", {}).get("items", []))
        source_item_ids = [
            self.canonical_id(item["id"], mode="sources")
            for item in payload.get("sourceItems", {}).get("items", [])
            if item.get("id")
        ]
        holding_institution_ids = [
            exemplar["institution_id"] for exemplar in exemplars if exemplar.get("institution_id") is not None
        ]
        repository = exemplars[0]["institution_label"] if exemplars else None
        shelfmark = exemplars[0]["shelfmark"] if exemplars else None

        return {
            "kind": "source",
            "canonical_id": canonical_id,
            "title": title,
            "titles": payload.get("label", {}),
            "standardized_title": standardized_title,
            "date_statements": date_statements,
            "catalog_identifiers": [
                {
                    "scheme": "rism",
                    "value": f"sources/{canonical_id}",
                    "source": "rism",
                }
            ],
            "external_refs": _ordered_unique_dicts(external_refs),
            "external_resources": external_resources,
            "relationships": relationships,
            "exemplars": exemplars,
            "repository": repository,
            "shelfmark": shelfmark,
            "source_item_ids": _ordered_unique(source_item_ids),
            "holding_institution_ids": _ordered_unique(holding_institution_ids),
            "created_at": payload.get("recordHistory", {}).get("created", {}).get("value"),
            "modified_at": payload.get("recordHistory", {}).get("updated", {}).get("value"),
        }

    def _decode_search_payload(self, text: str) -> dict[str, Any]:
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
            raise ValueError("Expected object payload from RISM search")
        marker = "initialData:"
        marker_index = text.find(marker)
        if marker_index == -1:
            raise ValueError("Could not decode RISM search payload")
        json_fragment = text[marker_index + len(marker) :].lstrip()
        decoder = json.JSONDecoder()
        payload, _ = decoder.raw_decode(json_fragment)
        if not isinstance(payload, dict):
            raise ValueError("Expected object payload from embedded RISM search data")
        return payload

    def _entry_label(self, entry: dict[str, Any]) -> str | None:
        return _select_multilingual_text(entry.get("label"))

    def _entry_value(self, entry: dict[str, Any]) -> str | None:
        value = entry.get("value")
        if isinstance(value, dict):
            return _select_multilingual_text(value)
        if value is None:
            return None
        return str(value)

    def _collect_external_resources(self, node: Any, path: str = "$") -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        if isinstance(node, dict):
            if node.get("type") == "rism:ExternalResource" and node.get("url"):
                collected.append(
                    {
                        "url": node["url"],
                        "label": _select_multilingual_text(node.get("label")),
                        "resource_type": node.get("resourceType"),
                        "context": path,
                    }
                )
            for key, value in node.items():
                next_path = f"{path}.{key}"
                if key == "externalResources" and isinstance(value, list):
                    for index, resource in enumerate(value):
                        collected.extend(self._collect_external_resources(resource, path=f"{next_path}[{index}]"))
                else:
                    collected.extend(self._collect_external_resources(value, path=next_path))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                collected.extend(self._collect_external_resources(value, path=f"{path}[{index}]"))
        return _ordered_unique_dicts(collected, unique_keys=("url", "context"))

    def _parse_relationships(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        relationships: list[dict[str, Any]] = []
        for item in items:
            related = item.get("relatedTo", {})
            relationships.append(
                {
                    "role": item.get("role", {}).get("value"),
                    "role_label": _select_multilingual_text(item.get("role", {}).get("label")),
                    "qualifier": item.get("qualifier", {}).get("value"),
                    "target_id": related.get("id"),
                    "target_type": related.get("type"),
                    "target_label": _select_multilingual_text(related.get("label")),
                }
            )
        return relationships

    def _parse_exemplars(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        exemplars: list[dict[str, Any]] = []
        for item in items:
            held_by = item.get("heldBy", {})
            summary = item.get("summary", [])
            shelfmark = None
            for summary_entry in summary:
                if self._entry_label(summary_entry) == "Shelfmark":
                    shelfmark = self._entry_value(summary_entry)
                    break
            exemplars.append(
                {
                    "holding_id": item.get("id"),
                    "label": _select_multilingual_text(item.get("label")),
                    "shelfmark": shelfmark,
                    "institution_id": held_by.get("id"),
                    "institution_label": _select_multilingual_text(held_by.get("label")),
                }
            )
        return exemplars

    def _bach_digital_ref(self, url: str) -> str | None:
        match = re.search(r"(BachDigital(?:Source|Work)_(?:source|work)_\d{8})", url)
        if match is None:
            return None
        return match.group(1)


def _ordered_unique_dicts(items: list[dict[str, Any]], unique_keys: tuple[str, ...] = ("source", "value", "url")) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    ordered: list[dict[str, Any]] = []
    for item in items:
        key = tuple(item.get(field) for field in unique_keys)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


RismConnector = RISMConnector
