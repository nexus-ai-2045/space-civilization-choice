"""Local proposal providers. Providers propose; the core validates and applies."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from .agents import AGENT_PREFERENCES
from .action_catalog import get_action


class ProposalProvider(Protocol):
    def propose(self, *, agent_id: str, year: int, seed: int, state: dict, parameters: dict) -> dict: ...


class DeterministicProposalProvider:
    provider_id = "deterministic_local_v1"

    def propose(self, *, agent_id: str, year: int, seed: int, state: dict, parameters: dict) -> dict:
        choices = AGENT_PREFERENCES[agent_id]
        material = json.dumps([seed, year, agent_id, state], sort_keys=True, separators=(",", ":"))
        index = int(hashlib.sha256(material.encode()).hexdigest()[:8], 16) % len(choices)
        return {
            "agent_id": agent_id,
            "action_id": choices[index],
            "priority": index,
            "rationale": "local deterministic proposal derived from current state",
            "provenance_type": "deterministic_core",
        }


PROPOSAL_KEYS = {"agent_id", "action_id", "priority", "rationale", "provenance_type"}


def validate_proposal(proposal: object, *, expected_agent_id: str) -> dict:
    """Validate untrusted provider output before deterministic arbitration."""
    if not isinstance(proposal, dict) or set(proposal) != PROPOSAL_KEYS:
        raise ValueError("proposal schema differs from the allowlist")
    if proposal["agent_id"] != expected_agent_id:
        raise ValueError("proposal agent_id differs from the requested agent")
    if not isinstance(proposal["action_id"], str):
        raise ValueError("proposal action_id must be a string")
    get_action(proposal["action_id"])
    if type(proposal["priority"]) is not int or not 0 <= proposal["priority"] <= 100:
        raise ValueError("proposal priority must be an integer in 0..100")
    for key, limit in (("rationale", 500), ("provenance_type", 64)):
        if not isinstance(proposal[key], str) or not proposal[key] or len(proposal[key]) > limit:
            raise ValueError(f"proposal {key} must be a non-empty bounded string")
    return dict(proposal)
