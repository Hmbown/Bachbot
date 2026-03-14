from __future__ import annotations

import json
from dataclasses import dataclass

from bachbot.claims.bundle import EvidenceBundle


@dataclass
class LLMRequest:
    mode: str
    system_prompt: str
    user_payload: dict
    question: str | None = None

    @property
    def prompt_text(self) -> str:
        return self.system_prompt

    def message_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"evidence_bundle": self.user_payload}
        if self.question:
            payload["question"] = self.question
        return payload

    def user_message(self) -> str:
        return json.dumps(self.message_payload(), indent=2, sort_keys=True)


def build_request(mode: str, system_prompt: str, bundle: EvidenceBundle, *, question: str | None = None) -> LLMRequest:
    return LLMRequest(mode=mode, system_prompt=system_prompt, user_payload=bundle.model_dump(mode="json"), question=question)
