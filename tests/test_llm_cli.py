from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from bachbot.analysis import analyze_graph
from bachbot.claims import build_evidence_bundle
from bachbot.cli.main import app
from bachbot.encodings import Normalizer


class FakePostResponse:
    def __init__(self, payload: dict[str, object], *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code < 400:
            return
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        response = httpx.Response(self.status_code, request=request, json=self._payload)
        raise httpx.HTTPStatusError("post failed", request=request, response=response)

    def json(self) -> dict[str, object]:
        return self._payload


def test_llm_run_dry_run_builds_request_from_score() -> None:
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]
    chorale_path = repo_root / "examples/chorales/simple_chorale.musicxml"

    result = runner.invoke(
        app,
        [
            "llm",
            "run",
            "scholar",
            str(chorale_path),
            "--question",
            "What does the cadence pattern suggest?",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "scholar"
    assert payload["executed"] is False
    assert payload["question"] == "What does the cadence pattern suggest?"
    assert payload["request"]["user_payload"]["question"] == "What does the cadence pattern suggest?"
    assert payload["request"]["user_payload"]["evidence_bundle"]["work_id"] == "simple_chorale"


def test_llm_run_execute_uses_openai_compatible_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    graph = Normalizer().normalize("tests/fixtures/chorales/simple_chorale.musicxml", work_id="FIXTURE-TEST")
    bundle = build_evidence_bundle(graph, analyze_graph(graph))
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    output_path = tmp_path / "llm-response.json"
    captured: dict[str, object] = {}

    def fake_post(url: str, *, headers=None, json=None, timeout=None):  # type: ignore[no-untyped-def]
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakePostResponse({"choices": [{"message": {"content": "Evidence-backed answer."}}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "llm",
            "run",
            "detective",
            "--bundle",
            str(bundle_path),
            "--execute",
            "--model",
            "gpt-test",
            "--api-key",
            "secret-token",
            "--base-url",
            "https://api.openai.com/v1",
            "--output",
            str(output_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output.strip() == str(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["executed"] is True
    assert payload["provider"] == "openai-compatible"
    assert payload["model"] == "gpt-test"
    assert payload["text"] == "Evidence-backed answer."
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert captured["json"]["messages"][0]["role"] == "system"
    assert "evidence_bundle" in json.loads(captured["json"]["messages"][1]["content"])


def test_llm_run_execute_requires_model_and_api_key(tmp_path: Path) -> None:
    graph = Normalizer().normalize("tests/fixtures/chorales/simple_chorale.musicxml", work_id="FIXTURE-TEST")
    bundle = build_evidence_bundle(graph, analyze_graph(graph))
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(app, ["llm", "run", "scholar", "--bundle", str(bundle_path), "--execute"])
    assert result.exit_code != 0
    assert "Live LLM execution requires --model or BACHBOT_LLM_MODEL." in result.output
