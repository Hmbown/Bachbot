from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from bachbot.encodings import Normalizer


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def authority_fixture_dir(fixture_dir: Path) -> Path:
    return fixture_dir / "authority"


@pytest.fixture
def simple_chorale_graph(fixture_dir):
    return Normalizer().normalize(fixture_dir / "chorales" / "simple_chorale.musicxml", work_id="BWV-TEST")


@pytest.fixture
def simple_cantus_graph(fixture_dir):
    return Normalizer().normalize(fixture_dir / "chorales" / "simple_cantus.musicxml", work_id="CANTUS-TEST")


class FakeHTTPResponse:
    def __init__(self, url: str, text: str, *, status_code: int = 200) -> None:
        self.url = url
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code < 400:
            return
        request = httpx.Request("GET", self.url)
        response = httpx.Response(self.status_code, request=request, text=self.text)
        raise httpx.HTTPStatusError(f"{self.status_code} error for {self.url}", request=request, response=response)


@pytest.fixture
def mock_authority_http(monkeypatch: pytest.MonkeyPatch, authority_fixture_dir: Path) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    bach_dir = authority_fixture_dir / "bach_digital"
    rism_dir = authority_fixture_dir / "rism"

    def _read_text(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def fake_get(url: str, params=None, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        final_url = url if params is None else str(httpx.URL(url, params=params))
        parsed = urlparse(final_url)
        query = parse_qs(parsed.query)
        header_map = dict(headers or {})
        requests.append({"url": final_url, "headers": header_map, "timeout": timeout})

        if parsed.netloc == "www.bach-digital.de":
            if parsed.path == "/servlets/solr/select":
                fq_values = query.get("fq", [])
                q_value = query.get("q", [""])[0]
                start_value = query.get("start", ["0"])[0]
                if any('link:"BachDigitalWork_work_00001262"' in value for value in fq_values):
                    return FakeHTTPResponse(final_url, _read_text(bach_dir / "linked_sources_for_00001262.json"))
                if any('link:"BachDigitalWork_work_00009999"' in value for value in fq_values):
                    return FakeHTTPResponse(final_url, json.dumps({"response": {"docs": []}}, indent=2))
                if q_value == "*:*" and any('"work"' in v for v in fq_values):
                    if start_value == "0":
                        return FakeHTTPResponse(final_url, _read_text(bach_dir / "search_all_works_page0.json"))
                    else:
                        return FakeHTTPResponse(final_url, _read_text(bach_dir / "search_all_works_page1.json"))
                if q_value == "canon":
                    return FakeHTTPResponse(final_url, _read_text(bach_dir / "search_work_free_text.json"))
                if q_value == 'musicrepo_work01:"BWV 1076"':
                    return FakeHTTPResponse(final_url, _read_text(bach_dir / "search_work_fielded.json"))
            if parsed.path.endswith("/BachDigitalWork_work_00001262"):
                if query.get("XSL.Style") == ["structure"]:
                    return FakeHTTPResponse(final_url, _read_text(bach_dir / "work_00001262.structure.xml"))
                if query.get("format") == ["jsonld"]:
                    return FakeHTTPResponse(final_url, _read_text(bach_dir / "work_00001262.jsonld.json"))
            if parsed.path.endswith("/BachDigitalWork_work_00009999"):
                if query.get("XSL.Style") == ["structure"]:
                    return FakeHTTPResponse(final_url, _read_text(bach_dir / "work_00009999.structure.xml"))
                if query.get("format") == ["jsonld"]:
                    return FakeHTTPResponse(final_url, _read_text(bach_dir / "work_00009999.jsonld.json"))
            if parsed.path.endswith("/BachDigitalSource_source_00000863"):
                if query.get("XSL.Style") == ["structure"]:
                    return FakeHTTPResponse(final_url, _read_text(bach_dir / "source_00000863.structure.xml"))
                if query.get("format") == ["jsonld"]:
                    return FakeHTTPResponse(final_url, _read_text(bach_dir / "source_00000863.jsonld.json"))

        if parsed.netloc == "rism.online":
            if parsed.path == "/search":
                if query.get("q") == ["bach"]:
                    return FakeHTTPResponse(final_url, _read_text(rism_dir / "search_sources_free_text.json"))
                if query.get("fq") == ["title:bach"]:
                    return FakeHTTPResponse(final_url, _read_text(rism_dir / "search_sources_fielded.json"))
            if parsed.path == "/sources/1001145660":
                if header_map.get("Accept") == "application/marcxml+xml":
                    return FakeHTTPResponse(final_url, _read_text(rism_dir / "marcxml_1001145660.xml"))
                return FakeHTTPResponse(final_url, _read_text(rism_dir / "resource_1001145660.json"))
            if parsed.path == "/sources/1001145661":
                if header_map.get("Accept") == "application/marcxml+xml":
                    return FakeHTTPResponse(final_url, "Not Acceptable", status_code=406)
                return FakeHTTPResponse(final_url, _read_text(rism_dir / "resource_1001145661.json"))

        raise AssertionError(f"Unexpected HTTP request in test fixture: {final_url}")

    monkeypatch.setattr(httpx, "get", fake_get)
    return requests
