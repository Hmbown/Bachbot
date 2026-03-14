"""Bach Digital connector."""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

from bachbot.registry.manifests import DatasetManifest

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
XLINK_TITLE = "{http://www.w3.org/1999/xlink}title"


def _ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _select_text(texts: dict[str, list[str]], preferred: tuple[str, ...] = ("en", "none", "de")) -> str | None:
    for language in preferred:
        values = texts.get(language, [])
        if values:
            return values[0]
    for values in texts.values():
        if values:
            return values[0]
    return None


class BachDigitalConnector:
    """Client for Bach Digital authority metadata."""

    base_url = "https://www.bach-digital.de"
    solr_url = f"{base_url}/servlets/solr/select"
    default_search_rows = 20
    timeout = 20.0

    def build_manifest(self, retrieved_at: str) -> DatasetManifest:
        return DatasetManifest(
            dataset_id="bach_digital",
            type="authority_metadata",
            source_url=self.base_url,
            retrieved_at=retrieved_at,
            license={
                "data": "ODC PDDL 1.0",
                "site_content": "CC BY-NC 4.0 unless otherwise noted",
            },
            catalog_revision="BWV3",
            notes=[
                "Use persistent work identifiers when available.",
                "Record export formats and last-changed fields per work.",
            ],
        )

    def validate_kind(self, kind: str) -> str:
        normalized = kind.strip().lower()
        if normalized not in {"work", "source"}:
            raise ValueError(f"Unsupported Bach Digital kind: {kind}")
        return normalized

    def canonical_id(self, value: str, *, kind: str) -> str:
        normalized_kind = self.validate_kind(kind)
        candidate = value.strip()
        if candidate.startswith("http://") or candidate.startswith("https://"):
            return self.parse_record_url(candidate, kind=normalized_kind)
        prefix = self._kind_prefix(normalized_kind)
        if candidate.startswith(prefix):
            return candidate
        match = re.search(r"(\d{1,8})$", candidate)
        if match is None:
            raise ValueError(f"Could not parse Bach Digital {normalized_kind} identifier: {value}")
        return f"{prefix}{match.group(1).zfill(8)}"

    def parse_record_url(self, url: str, *, kind: str | None = None) -> str:
        parsed = urlparse(url)
        match = re.search(r"/receive/(BachDigital(?:Work|Source)_(?:work|source)_\d{8})", parsed.path)
        if match is None:
            raise ValueError(f"Could not parse Bach Digital record URL: {url}")
        canonical_id = match.group(1)
        inferred_kind = "work" if canonical_id.startswith("BachDigitalWork_") else "source"
        if kind is not None and self.validate_kind(kind) != inferred_kind:
            raise ValueError(f"Bach Digital URL kind mismatch: expected {kind}, got {inferred_kind}")
        return canonical_id

    def persistent_url(self, canonical_id: str) -> str:
        return f"{self.base_url}/receive/{canonical_id}"

    def structure_url(self, canonical_id: str) -> str:
        return f"{self.persistent_url(canonical_id)}?XSL.Style=structure"

    def jsonld_url(self, canonical_id: str) -> str:
        return f"{self.persistent_url(canonical_id)}?format=jsonld"

    def search(self, *, kind: str, query: str, query_field: str | None = None,
               rows: int | None = None, start: int = 0) -> dict[str, Any]:
        normalized_kind = self.validate_kind(kind)
        params: dict[str, Any] = {
            "q": self._build_search_query(query, query_field=query_field),
            "fq": f'objectType:"{normalized_kind}"',
            "rows": str(rows or self.default_search_rows),
            "start": str(start),
            "wt": "json",
        }
        response = httpx.get(self.solr_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = json.loads(response.text)
        resp = payload.get("response", {})
        docs = resp.get("docs", [])
        num_found = resp.get("numFound", 0)
        raw_record_ids = [
            self.canonical_id(doc.get("returnId") or doc.get("id"), kind=normalized_kind)
            for doc in docs
            if doc.get("returnId") or doc.get("id")
        ]
        return {
            "request_url": str(response.url),
            "request_params": params,
            "response_payload": payload,
            "raw_record_ids": raw_record_ids,
            "record_ids": _ordered_unique(raw_record_ids),
            "num_found": num_found,
        }

    def linked_source_ids(self, work_id: str) -> dict[str, Any]:
        canonical_work_id = self.canonical_id(work_id, kind="work")
        params: dict[str, Any] = {
            "q": "*:*",
            "fq": [r'objectType:"source"', f'link:"{canonical_work_id}"'],
            "rows": "1000",
            "wt": "json",
        }
        response = httpx.get(self.solr_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = json.loads(response.text)
        docs = payload.get("response", {}).get("docs", [])
        raw_record_ids = [
            self.canonical_id(doc.get("returnId") or doc.get("id"), kind="source")
            for doc in docs
            if doc.get("returnId") or doc.get("id")
        ]
        return {
            "request_url": str(response.url),
            "request_params": params,
            "response_payload": payload,
            "raw_record_ids": raw_record_ids,
            "record_ids": _ordered_unique(raw_record_ids),
        }

    def fetch_structure_xml(self, canonical_id: str) -> dict[str, Any]:
        response = httpx.get(self.structure_url(canonical_id), timeout=self.timeout)
        response.raise_for_status()
        return {"url": str(response.url), "text": response.text}

    def fetch_jsonld_payload(self, canonical_id: str) -> dict[str, Any]:
        response = httpx.get(
            self.jsonld_url(canonical_id),
            headers={"Accept": "application/ld+json, application/json;q=0.9, text/html;q=0.1"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return {
            "url": str(response.url),
            "payload": self._decode_json_payload(response.text),
        }

    def parse_structure_xml(self, xml_text: str, *, kind: str) -> dict[str, Any]:
        normalized_kind = self.validate_kind(kind)
        if normalized_kind == "work":
            return self._parse_work_xml(xml_text)
        return self._parse_source_xml(xml_text)

    def _kind_prefix(self, kind: str) -> str:
        normalized_kind = self.validate_kind(kind)
        return "BachDigitalWork_work_" if normalized_kind == "work" else "BachDigitalSource_source_"

    def _build_search_query(self, query: str, *, query_field: str | None = None) -> str:
        if query_field is None:
            return query
        escaped = query.replace('"', '\\"')
        return f'{query_field}:"{escaped}"'

    def _decode_json_payload(self, text: str) -> Any:
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            return json.loads(text)
        match = re.search(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if match is None:
            return {"_raw_html": True, "_note": "No JSON-LD found in HTML response"}
        payload_text = html.unescape(match.group(1)).strip()
        if not payload_text:
            return {"_raw_html": True, "_note": "Empty JSON-LD block in HTML response"}
        try:
            return json.loads(payload_text)
        except json.JSONDecodeError:
            return {"_raw_html": True, "_note": "Invalid JSON in JSON-LD block"}

    def _parse_work_xml(self, xml_text: str) -> dict[str, Any]:
        root = ET.fromstring(xml_text)
        record = root.find(".//mycoreobject")
        if record is None:
            raise ValueError("Bach Digital work XML missing mycoreobject")
        metadata = record.find("metadata")
        if metadata is None:
            raise ValueError("Bach Digital work XML missing metadata")

        canonical_id = record.attrib["ID"]
        catalog_scheme = self._catalog_scheme(self._texts_by_lang(metadata, "work24"))
        catalog_values = self._non_x_language_texts(metadata, "work01")
        title_texts = self._texts_by_lang(metadata, "work02")
        external_refs: list[dict[str, Any]] = []
        for entry in self._typed_text_entries(metadata, "work16"):
            value = entry["text"]
            if not value:
                continue
            external_refs.append(
                {
                    "source": entry.get("type") or entry.get("lang") or "external",
                    "value": value,
                    "url": self._external_url(entry.get("type") or entry.get("lang"), value),
                }
            )

        return {
            "kind": "work",
            "canonical_id": canonical_id,
            "title": _select_text(title_texts) or record.attrib.get("label"),
            "titles": title_texts,
            "date_statements": self._history_entries(metadata, "work04"),
            "catalog_identifiers": [
                {"scheme": "bach_digital", "value": canonical_id, "source": "bach_digital"},
                *[
                    {
                        "scheme": catalog_scheme,
                        "value": value,
                        "revision": "BWV3" if catalog_scheme == "bwv" else None,
                        "source": "bach_digital",
                    }
                    for value in catalog_values
                ],
            ],
            "external_refs": external_refs,
            "genre": _select_text(self._texts_by_lang(metadata, "work19")),
            "created_at": self._service_date(record, "createdate"),
            "modified_at": self._service_date(record, "modifydate"),
            "license": self._service_flag(record, "license"),
        }

    def _parse_source_xml(self, xml_text: str) -> dict[str, Any]:
        root = ET.fromstring(xml_text)
        record = root.find(".//mycoreobject")
        if record is None:
            raise ValueError("Bach Digital source XML missing mycoreobject")
        metadata = record.find("metadata")
        if metadata is None:
            raise ValueError("Bach Digital source XML missing metadata")

        canonical_id = record.attrib["ID"]
        repository_texts = self._texts_by_lang(metadata, "source38")
        source_titles = self._texts_by_lang(metadata, "source01")
        catalog_scheme = self._catalog_scheme(self._texts_by_lang(metadata, "source42"))
        catalog_values = self._non_x_language_texts(metadata, "source02")
        linked_work_ids = self._link_targets(metadata, "source32")
        external_refs: list[dict[str, Any]] = []
        repository_sigla = self._texts_for_language(metadata, "source38", "x-rism")
        repository_isil = self._texts_for_language(metadata, "source38", "x-isil")
        for value in repository_sigla:
            external_refs.append({"source": "rism_siglum", "value": value, "url": None})
        for value in repository_isil:
            external_refs.append({"source": "isil", "value": value, "url": None})
        for entry in self._typed_text_entries(metadata, "source46"):
            value = entry["text"]
            if not value:
                continue
            external_refs.append(
                {
                    "source": entry.get("type") or "external",
                    "value": value,
                    "url": self._external_url(entry.get("type"), value),
                }
            )
        for href in self._external_links(metadata, "source40"):
            external_refs.append({"source": "digitization", "value": href, "url": href})

        return {
            "kind": "source",
            "canonical_id": canonical_id,
            "title": _select_text(source_titles) or root.attrib.get("classmark") or record.attrib.get("label"),
            "titles": source_titles,
            "repository": _select_text(repository_texts, preferred=("en", "de", "none")),
            "shelfmark": root.attrib.get("classmark"),
            "date_statements": [
                *self._non_empty_text_entries(metadata, "source27"),
                *self._history_entries(metadata, "source12"),
            ],
            "catalog_identifiers": [
                {"scheme": "bach_digital", "value": canonical_id, "source": "bach_digital"},
                *[
                    {
                        "scheme": catalog_scheme,
                        "value": value,
                        "revision": "BWV3" if catalog_scheme == "bwv" else None,
                        "source": "bach_digital",
                    }
                    for value in catalog_values
                ],
            ],
            "external_refs": external_refs,
            "linked_work_ids": linked_work_ids,
            "created_at": self._service_date(record, "createdate"),
            "modified_at": self._service_date(record, "modifydate"),
            "license": self._service_flag(record, "license"),
        }

    def _texts_by_lang(self, metadata: ET.Element, tag_name: str) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}
        for node in metadata.findall(f".//{tag_name}"):
            text = (node.text or "").strip()
            if not text:
                continue
            language = node.attrib.get(XML_LANG, "none")
            values.setdefault(language, []).append(text)
        return values

    def _texts_for_language(self, metadata: ET.Element, tag_name: str, language: str) -> list[str]:
        return self._texts_by_lang(metadata, tag_name).get(language, [])

    def _non_x_language_texts(self, metadata: ET.Element, tag_name: str) -> list[str]:
        values: list[str] = []
        for language, items in self._texts_by_lang(metadata, tag_name).items():
            if language.startswith("x-"):
                continue
            values.extend(items)
        return _ordered_unique(values)

    def _typed_text_entries(self, metadata: ET.Element, tag_name: str) -> list[dict[str, str | None]]:
        entries: list[dict[str, str | None]] = []
        for node in metadata.findall(f".//{tag_name}"):
            text = (node.text or "").strip()
            if not text:
                continue
            entries.append(
                {
                    "text": text,
                    "lang": node.attrib.get(XML_LANG),
                    "type": node.attrib.get("type"),
                }
            )
        return entries

    def _non_empty_text_entries(self, metadata: ET.Element, tag_name: str) -> list[dict[str, str | None]]:
        entries: list[dict[str, str | None]] = []
        for node in metadata.findall(f".//{tag_name}"):
            text = (node.text or "").strip()
            if not text:
                continue
            entries.append({"text": text, "lang": node.attrib.get(XML_LANG)})
        return entries

    def _history_entries(self, metadata: ET.Element, tag_name: str) -> list[dict[str, str | None]]:
        entries: list[dict[str, str | None]] = []
        for node in metadata.findall(f".//{tag_name}"):
            text_map: dict[str, list[str]] = {}
            for text_node in node.findall("text"):
                text = (text_node.text or "").strip()
                if not text:
                    continue
                language = text_node.attrib.get(XML_LANG, "none")
                text_map.setdefault(language, []).append(text)
            entries.append(
                {
                    "display": _select_text(text_map),
                    "start": self._child_text(node, "von"),
                    "end": self._child_text(node, "bis"),
                    "calendar": self._child_text(node, "calendar"),
                }
            )
        return [entry for entry in entries if entry["display"] or entry["start"] or entry["end"]]

    def _external_links(self, metadata: ET.Element, tag_name: str) -> list[str]:
        hrefs: list[str] = []
        for node in metadata.findall(f".//{tag_name}"):
            href = node.attrib.get(XLINK_HREF)
            if href:
                hrefs.append(href)
        return _ordered_unique(hrefs)

    def _link_targets(self, metadata: ET.Element, tag_name: str) -> list[str]:
        targets: list[str] = []
        for node in metadata.findall(f".//{tag_name}"):
            href = node.attrib.get(XLINK_HREF)
            if href:
                targets.append(href)
        return _ordered_unique(targets)

    def _catalog_scheme(self, texts: dict[str, list[str]]) -> str:
        flattened = [item.upper() for values in texts.values() for item in values]
        if any("BWV" in item for item in flattened):
            return "bwv"
        return "catalog"

    def _child_text(self, node: ET.Element, tag_name: str) -> str | None:
        child = node.find(tag_name)
        if child is None or child.text is None:
            return None
        text = child.text.strip()
        return text or None

    def _service_date(self, record: ET.Element, date_type: str) -> str | None:
        service = record.find("service")
        if service is None:
            return None
        for node in service.findall(".//servdate"):
            if node.attrib.get("type") == date_type:
                text = (node.text or "").strip()
                return text or None
        return None

    def _service_flag(self, record: ET.Element, flag_type: str) -> str | None:
        service = record.find("service")
        if service is None:
            return None
        for node in service.findall(".//servflag"):
            if node.attrib.get("type") == flag_type:
                text = (node.text or "").strip()
                return text or None
        return None

    def _external_url(self, ref_type: str | None, value: str) -> str | None:
        if ref_type == "gnd":
            return f"https://d-nb.info/gnd/{value}"
        if ref_type == "rism":
            return f"https://rism.online/sources/{value}"
        return None


BachdigitalConnector = BachDigitalConnector
