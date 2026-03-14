from __future__ import annotations

import time
from pathlib import Path

import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from bachbot.api import app as api_app
from bachbot.cli.main import app


def _fixture_text(name: str) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "tests" / "fixtures" / "chorales" / name
    return path.read_text(encoding="utf-8")


def test_api_docs_and_health_are_available() -> None:
    client = TestClient(api_app)

    docs_response = client.get("/docs")
    health_response = client.get("/health")

    assert docs_response.status_code == 200
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"


def test_analyze_endpoint_returns_json_under_latency_budget() -> None:
    client = TestClient(api_app)
    started = time.perf_counter()
    response = client.post(
        "/analyze",
        json={"musicxml": _fixture_text("simple_chorale.musicxml"), "work_id": "simple_chorale"},
    )
    elapsed = time.perf_counter() - started

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["analysis_report"]["work_id"] == "simple_chorale"
    assert payload["evidence_bundle"]["work_id"] == "simple_chorale"
    assert elapsed < 2.0


def test_compose_and_evaluate_endpoints_return_quality_json() -> None:
    client = TestClient(api_app)

    compose_response = client.post(
        "/compose",
        json={"musicxml": _fixture_text("simple_cantus.musicxml"), "work_id": "simple_cantus"},
    )
    evaluate_response = client.post(
        "/evaluate",
        json={"musicxml": _fixture_text("simple_chorale.musicxml"), "work_id": "simple_chorale"},
    )

    assert compose_response.status_code == 200, compose_response.text
    compose_payload = compose_response.json()
    assert compose_payload["artifact"]["artifact_class"] == "bachbot-study"
    assert "validation" in compose_payload["report"]

    assert evaluate_response.status_code == 200, evaluate_response.text
    metrics = evaluate_response.json()["metrics"]
    assert "parallel_5ths" in metrics
    assert "passed_validation" in metrics


def test_corpus_lookup_search_and_error_handling() -> None:
    client = TestClient(api_app)

    detail_response = client.get("/corpus/BWV269")
    search_response = client.get("/corpus/search", params={"key": "G major", "cadence_type": "cadential", "limit": 3})
    missing_response = client.get("/corpus/NOPE999")
    invalid_response = client.post("/analyze", json={"musicxml": "<not-musicxml />"})

    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert detail_payload["chorale_id"] == "BWV269"
    assert "Jesu, der du meine Seele" in detail_payload["title"]

    assert search_response.status_code == 200, search_response.text
    search_payload = search_response.json()
    assert search_payload["count"] >= 1
    assert all(item["key"] == "G major" for item in search_payload["results"])
    assert all("cadential" in item["cadence_types"] for item in search_payload["results"])

    assert missing_response.status_code == 404
    assert invalid_response.status_code == 400


def test_serve_command_invokes_uvicorn(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    def fake_run(target: str, *, host: str, port: int, reload: bool, factory: bool) -> None:
        calls.update({"target": target, "host": host, "port": port, "reload": reload, "factory": factory})

    monkeypatch.setattr("bachbot.cli.serve.uvicorn.run", fake_run)

    result = runner.invoke(app, ["serve", "--host", "0.0.0.0", "--port", "8000"])

    assert result.exit_code == 0, result.output
    assert calls == {
        "target": "bachbot.api:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": False,
        "factory": False,
    }


def test_docker_compose_exposes_api_service() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    compose_path = repo_root / "docker-compose.yml"

    payload = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    assert "bachbot-api" in payload["services"]
    service = payload["services"]["bachbot-api"]
    assert "8000:8000" in service["ports"]
    assert "bachbot" in service["command"]
    assert "serve" in service["command"]
