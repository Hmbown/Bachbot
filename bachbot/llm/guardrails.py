from __future__ import annotations

from pathlib import Path

from bachbot.claims.bundle import EvidenceBundle


def load_prompt(name: str) -> str:
    return (Path(__file__).parent / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def validate_bundle_for_llm(bundle: EvidenceBundle) -> None:
    if not bundle.deterministic_findings or not bundle.passage_refs:
        raise ValueError("Evidence bundle is incomplete for LLM use")

