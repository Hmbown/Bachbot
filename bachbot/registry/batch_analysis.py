"""Batch LLM analysis across ingested corpus evidence bundles."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bachbot.claims import EvidenceBundle
from bachbot.llm import execute_mode_response, prepare_mode_response
from bachbot.registry.storage import BachbotStorage


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def batch_llm_analysis(
    *,
    dataset: str,
    mode: str = "scholar",
    dry_run: bool = True,
    question: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    storage = BachbotStorage(dataset).ensure()
    derived_root = Path(storage.derived_dir)
    bundle_paths = sorted(derived_root.glob("*.evidence_bundle.json"))

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    processed_at = _timestamp()

    for bundle_path in bundle_paths:
        artifact_stem = bundle_path.name[: -len(".evidence_bundle.json")]
        try:
            bundle = EvidenceBundle.model_validate(
                json.loads(bundle_path.read_text(encoding="utf-8"))
            )
            if dry_run:
                response = prepare_mode_response(mode, bundle, question=question)
            else:
                response = execute_mode_response(
                    mode,
                    bundle,
                    question=question,
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    timeout_seconds=timeout_seconds,
                )

            output = {
                "mode": response.mode,
                "executed": response.executed,
                "provider": response.provider,
                "model": response.model,
                "text": response.text,
                "question": question,
                "bundle_path": str(bundle_path),
                "artifact_stem": artifact_stem,
                "processed_at": processed_at,
                "request": {
                    "system_prompt": response.request.system_prompt,
                    "user_payload": response.request.message_payload(),
                },
            }
            output_path = derived_root / f"{artifact_stem}.llm_{mode}.json"
            output_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
            results.append({**output, "output_path": str(output_path)})
        except Exception as exc:
            failures.append({
                "artifact_stem": artifact_stem,
                "bundle_path": str(bundle_path),
                "error": str(exc),
            })

    return {
        "dataset": dataset,
        "mode": mode,
        "dry_run": dry_run,
        "processed_count": len(results),
        "failure_count": len(failures),
        "results": results,
        "failures": failures,
        "processed_at": processed_at,
    }
