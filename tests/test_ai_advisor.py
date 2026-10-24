from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_civilization.ai_advisor import PHASE1_ALLOWED_ACTIONS, propose_action


CONTEXT = {"year": 2030, "branch": "domestic_autonomy", "axes": {"public_legitimacy": 54}}


def test_missing_key_uses_stable_allowed_fallback():
    first = propose_action(CONTEXT, environ={})
    second = propose_action(CONTEXT, environ={})

    assert first == second
    assert first.action in PHASE1_ALLOWED_ACTIONS
    assert first.source == "deterministic_fallback"


def test_structured_response_returns_ai_proposal_without_mutating_context():
    before = {"year": CONTEXT["year"], "branch": CONTEXT["branch"], "axes": dict(CONTEXT["axes"])}
    captured = {}

    def transport(payload, timeout):
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {"output_text": '{"action":"expand_maintainer_training","rationale":"技能継承を強化します。"}'}

    proposal = propose_action(CONTEXT, environ={"OPENAI_API_KEY": "test-secret"}, transport=transport)

    assert proposal.action == "expand_maintainer_training"
    assert proposal.rationale == "技能継承を強化します。"
    assert proposal.source == "openai"
    assert CONTEXT == before
    assert captured["timeout"] == 8.0
    assert captured["payload"]["store"] is False
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert "test-secret" not in str(captured["payload"])


def test_configurable_model_is_sent_to_responses_api():
    captured = {}

    def transport(payload, _timeout):
        captured.update(payload)
        return {"output_text": '{"action":"qualify_redundant_component_supply","rationale":"供給途絶に備えます。"}'}

    propose_action(
        CONTEXT,
        model="configured-model",
        environ={"OPENAI_API_KEY": "test-secret"},
        transport=transport,
    )

    assert captured["model"] == "configured-model"


def test_timeout_and_bad_responses_fail_closed_to_same_fallback():
    expected = propose_action(CONTEXT, environ={})

    def timeout_transport(_payload, _timeout):
        raise TimeoutError("request timed out with untrusted details")

    invalid_responses = [
        timeout_transport,
        lambda _payload, _timeout: {"output_text": "not-json"},
        lambda _payload, _timeout: {
            "output_text": '{"action":"launch_attack","rationale":"許可されない行動"}'
        },
        lambda _payload, _timeout: {
            "output_text": '{"action":"expand_maintainer_training","rationale":"","extra":true}'
        },
    ]

    for transport in invalid_responses:
        actual = propose_action(
            CONTEXT,
            environ={"OPENAI_API_KEY": "must-not-leak"},
            transport=transport,
        )
        assert actual == expected


def test_nested_responses_output_is_supported():
    def transport(_payload, _timeout):
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"action":"operate_with_domestic_maintenance_chain","rationale":"運用継続性を確保します。"}',
                        }
                    ],
                }
            ]
        }

    proposal = propose_action(CONTEXT, environ={"OPENAI_API_KEY": "test-secret"}, transport=transport)

    assert proposal.action == "operate_with_domestic_maintenance_chain"
    assert proposal.source == "openai"
