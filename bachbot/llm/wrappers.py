from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from bachbot.claims.bundle import EvidenceBundle
from bachbot.llm.adapters import LLMRequest, build_request
from bachbot.llm.guardrails import load_prompt, validate_bundle_for_llm


@dataclass
class LLMResponse:
    mode: str
    request: LLMRequest
    text: str
    executed: bool = False
    provider: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    timeout_seconds: float = 60.0


def prepare_mode_response(mode: str, bundle: EvidenceBundle, *, question: str | None = None) -> LLMResponse:
    validate_bundle_for_llm(bundle)
    request = build_request(mode, load_prompt(mode), bundle, question=question)
    return LLMResponse(
        mode=mode,
        request=request,
        text=(
            f"[dry-run] Prepared {mode} prompt with {len(bundle.passage_refs)} passage refs and "
            f"{len(bundle.deterministic_findings.get('harmony', []))} harmonic events."
        ),
        executed=False,
    )


def build_prompt_request(mode: str, bundle: EvidenceBundle, *, question: str | None = None) -> LLMRequest:
    validate_bundle_for_llm(bundle)
    return build_request(mode, load_prompt(mode), bundle, question=question)


def execute_mode_response(
    mode: str,
    bundle: EvidenceBundle,
    *,
    question: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 60.0,
) -> LLMResponse:
    validate_bundle_for_llm(bundle)
    request = build_request(mode, load_prompt(mode), bundle, question=question)
    config = resolve_provider_config(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
    if config.provider != "openai-compatible":
        raise ValueError(f"Unsupported LLM provider: {config.provider}")
    text = _execute_openai_compatible(request, config)
    return LLMResponse(mode=mode, request=request, text=text, executed=True, provider=config.provider, model=config.model)


def resolve_provider_config(
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 60.0,
) -> LLMProviderConfig:
    resolved_provider = provider or os.getenv("BACHBOT_LLM_PROVIDER", "openai-compatible")
    resolved_model = model or os.getenv("BACHBOT_LLM_MODEL") or os.getenv("OPENAI_MODEL")
    if not resolved_model:
        raise ValueError("Live LLM execution requires --model or BACHBOT_LLM_MODEL.")
    resolved_api_key = api_key or os.getenv("BACHBOT_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not resolved_api_key:
        raise ValueError("Live LLM execution requires --api-key or BACHBOT_LLM_API_KEY.")
    resolved_base_url = base_url or os.getenv("BACHBOT_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    if timeout_seconds <= 0:
        raise ValueError("LLM timeout_seconds must be positive.")
    return LLMProviderConfig(
        provider=resolved_provider,
        model=resolved_model,
        api_key=resolved_api_key,
        base_url=resolved_base_url,
        timeout_seconds=timeout_seconds,
    )


def _execute_openai_compatible(request: LLMRequest, config: LLMProviderConfig) -> str:
    endpoint = config.base_url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/chat/completions"
    response = httpx.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={
            "model": config.model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_message()},
            ],
        },
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    return _extract_openai_text(payload)


def _extract_openai_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response did not include any choices.")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("LLM response choice payload was malformed.")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("LLM response did not include a message payload.")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
        if text_parts:
            return "".join(text_parts)
    raise ValueError("LLM response content was empty or malformed.")
