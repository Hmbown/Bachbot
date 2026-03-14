"""LLM CLI commands."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import typer

from bachbot.analysis import analyze_graph
from bachbot.claims import EvidenceBundle, build_evidence_bundle
from bachbot.cli.io import emit_json
from bachbot.encodings import Normalizer
from bachbot.llm import execute_mode_response, prepare_mode_response
from bachbot.registry.batch_analysis import batch_llm_analysis

app = typer.Typer(help="Evidence-first LLM commentary commands.")


class LLMMode(str, Enum):
    scholar = "scholar"
    detective = "detective"
    pedagogy = "pedagogy"
    composer = "composer"
    aiml = "aiml"


@app.command("run")
def run_mode(
    mode: LLMMode,
    score_path: Path | None = typer.Argument(None),
    bundle: Path | None = typer.Option(None, "--bundle", help="Existing evidence bundle JSON to use instead of a score path."),
    work_id: str | None = typer.Option(None, "--work-id", help="Optional work identifier when normalizing a score path."),
    question: str | None = typer.Option(None, "--question", help="Optional user question to append to the evidence bundle request."),
    execute: bool = typer.Option(
        False,
        "--execute/--dry-run",
        help="Execute against a configured LLM provider instead of only preparing the evidence-bounded request.",
    ),
    provider: str | None = typer.Option(None, "--provider", help="Live provider name; currently only openai-compatible is supported."),
    model: str | None = typer.Option(None, "--model", help="Live model name for --execute."),
    base_url: str | None = typer.Option(None, "--base-url", help="Override the OpenAI-compatible API base URL."),
    api_key: str | None = typer.Option(None, "--api-key", help="Override the live API key instead of reading environment variables."),
    timeout: float = typer.Option(60.0, "--timeout", min=0.1, help="HTTP timeout in seconds for live provider calls."),
    output: Path | None = typer.Option(None, "--output", help="Write the full LLM request/response payload to a JSON file."),
) -> None:
    """Prepare or execute an evidence-bounded LLM response for a score or bundle."""

    try:
        evidence_bundle = _load_bundle(score_path=score_path, bundle_path=bundle, work_id=work_id)
        if execute:
            response = execute_mode_response(
                mode.value,
                evidence_bundle,
                question=question,
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
                timeout_seconds=timeout,
            )
        else:
            response = prepare_mode_response(mode.value, evidence_bundle, question=question)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    emit_json(
        {
            "mode": response.mode,
            "executed": response.executed,
            "provider": response.provider,
            "model": response.model,
            "question": response.request.question,
            "text": response.text,
            "request": {
                "system_prompt": response.request.system_prompt,
                "user_payload": response.request.message_payload(),
            },
        },
        output=output,
    )


@app.command("batch")
def batch_command(
    dataset: str,
    mode: LLMMode = typer.Option(LLMMode.scholar, "--mode"),
    execute: bool = typer.Option(
        False,
        "--execute/--dry-run",
        help="Execute against a configured LLM provider instead of dry-run.",
    ),
    question: str | None = typer.Option(None, "--question"),
    provider: str | None = typer.Option(None, "--provider"),
    model: str | None = typer.Option(None, "--model"),
    base_url: str | None = typer.Option(None, "--base-url"),
    api_key: str | None = typer.Option(None, "--api-key"),
    timeout: float = typer.Option(60.0, "--timeout", min=0.1),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    """Run LLM analysis across all evidence bundles for a dataset."""
    try:
        result = batch_llm_analysis(
            dataset=dataset,
            mode=mode.value,
            dry_run=not execute,
            question=question,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(
        f"Processed {result['processed_count']} bundles with {result['failure_count']} failure(s) "
        f"({'executed' if not result['dry_run'] else 'dry-run'})"
    )
    if output is not None:
        emit_json(result, output=output)


def _load_bundle(*, score_path: Path | None, bundle_path: Path | None, work_id: str | None) -> EvidenceBundle:
    if score_path is None and bundle_path is None:
        raise typer.BadParameter("Provide either SCORE_PATH or --bundle.")
    if score_path is not None and bundle_path is not None:
        raise typer.BadParameter("Use either SCORE_PATH or --bundle, not both.")
    if bundle_path is not None:
        return EvidenceBundle.model_validate(json.loads(bundle_path.read_text(encoding="utf-8")))
    assert score_path is not None
    graph = Normalizer().normalize(score_path, work_id=work_id)
    analysis = analyze_graph(graph)
    return build_evidence_bundle(graph, analysis)
