"""AIは行動を提案するだけで、状態遷移は決定論コアに委ねる。"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping

from .simulation import PHASE1_ALLOWED_ACTIONS, canonical_json


RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_RATIONALE_LENGTH = 240
PROMPT_VERSION = "hackathon-advisor-v1"


@dataclass(frozen=True)
class ActionProposal:
    action: str
    rationale: str
    source: str
    model: str
    prompt_version: str
    validation_state: str
    fallback_reason: str | None = None

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


Transport = Callable[[dict[str, Any], float], Mapping[str, Any]]


def _fallback(context: Mapping[str, Any], model: str) -> ActionProposal:
    """同じ入力には常に同じ許可済み行動を返す。"""
    actions = sorted(PHASE1_ALLOWED_ACTIONS)
    digest = hashlib.sha256(canonical_json(context).encode("utf-8")).digest()
    action = actions[int.from_bytes(digest[:8], "big") % len(actions)]
    return ActionProposal(
        action=action,
        rationale="AI提案を利用できないため、入力ハッシュから許可済み行動を決定しました。",
        source="deterministic_fallback",
        model=model,
        prompt_version=PROMPT_VERSION,
        validation_state="accepted_for_run",
        fallback_reason="unavailable_or_invalid",
    )


def _response_payload(model: str, context: Mapping[str, Any]) -> dict[str, Any]:
    actions = sorted(PHASE1_ALLOWED_ACTIONS)
    return {
        "model": model,
        "store": False,
        "instructions": (
            "あなたは宇宙文明シミュレーターの助言役です。状態を変更せず、"
            "許可された行動を1つだけ提案し、短い日本語の根拠を返してください。"
        ),
        "input": canonical_json(context),
        "max_output_tokens": 160,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "civilization_action_proposal",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "action": {"type": "string", "enum": actions},
                        "rationale": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": MAX_RATIONALE_LENGTH,
                        },
                    },
                    "required": ["action", "rationale"],
                },
            }
        },
    }


def _post_response(payload: dict[str, Any], api_key: str, timeout: float) -> Mapping[str, Any]:
    request = urllib.request.Request(
        RESPONSES_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_output_text(response: Mapping[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    output = response.get("output")
    if not isinstance(output, list):
        raise ValueError("response output is missing")
    texts: list[str] = []
    for item in output:
        if not isinstance(item, Mapping):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, Mapping) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    if not texts:
        raise ValueError("response text is missing")
    return "".join(texts)


def _validate_proposal(raw: Any) -> ActionProposal:
    if not isinstance(raw, dict) or set(raw) != {"action", "rationale"}:
        raise ValueError("proposal schema mismatch")
    action = raw["action"]
    rationale = raw["rationale"]
    if action not in PHASE1_ALLOWED_ACTIONS:
        raise ValueError("action is not allowed")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > MAX_RATIONALE_LENGTH:
        raise ValueError("rationale is invalid")
    return ActionProposal(
        action=action,
        rationale=rationale.strip(),
        source="openai",
        model="",
        prompt_version=PROMPT_VERSION,
        validation_state="accepted_for_run",
    )


def propose_action(
    context: Mapping[str, Any],
    *,
    model: str | None = None,
    timeout: float = 8.0,
    environ: Mapping[str, str] | None = None,
    transport: Transport | None = None,
) -> ActionProposal:
    """許可済み行動を提案する。API失敗時は例外や秘密を外へ出さずfallbackする。"""
    env = os.environ if environ is None else environ
    api_key = env.get("OPENAI_API_KEY", "").strip()
    selected_model = model or env.get("OPENAI_MODEL", DEFAULT_MODEL)
    if not api_key:
        return _fallback(context, selected_model)
    payload = _response_payload(selected_model, context)
    if transport is None:
        transport = lambda body, seconds: _post_response(body, api_key, seconds)
    try:
        response = transport(payload, timeout)
        raw = json.loads(_extract_output_text(response))
        proposal = _validate_proposal(raw)
        return ActionProposal(**{**proposal.to_dict(), "model": selected_model})
    except Exception:
        # HTTP本文や例外にはsecretや未信頼レスポンスが含まれ得るため、外へ伝播しない。
        return _fallback(context, selected_model)
