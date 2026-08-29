"""Local proposal providers. Providers propose; the core validates and applies."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from .agents import AGENT_PREFERENCES
from .action_catalog import get_action


ALLOWED_PROVENANCE_TYPES = frozenset(
    {
        "official_source",
        "academic_source",
        "third_party_public_source",
        "human_input",
        "deterministic_core",
        "llm",
    }
)


class ProposalProvider(Protocol):
    def propose(self, *, agent_id: str, year: int, seed: int, state: dict, parameters: dict) -> dict: ...


class DeterministicProposalProvider:
    provider_id = "deterministic_local_v1"
    # Core-configured identity only; never read from untrusted response bodies.
    provenance_type = "deterministic_core"

    def propose(self, *, agent_id: str, year: int, seed: int, state: dict, parameters: dict) -> dict:
        choices = AGENT_PREFERENCES[agent_id]
        material = json.dumps([seed, year, agent_id, state], sort_keys=True, separators=(",", ":"))
        index = int(hashlib.sha256(material.encode()).hexdigest()[:8], 16) % len(choices)
        return {
            "agent_id": agent_id,
            "action_id": choices[index],
            "priority": index,
            "rationale": "local deterministic proposal derived from current state",
        }


# Providers may omit provenance_type; the core always assigns it.
REQUIRED_PROPOSAL_KEYS = frozenset({"agent_id", "action_id", "priority", "rationale"})
OPTIONAL_PROPOSAL_KEYS = frozenset({"provenance_type"})


def derive_provenance_type(provider: object) -> str:
    """Assign provenance from the configured provider, never from response payload."""
    declared = getattr(provider, "provenance_type", None)
    if isinstance(declared, str) and declared in ALLOWED_PROVENANCE_TYPES:
        return declared
    provider_id = getattr(provider, "provider_id", None)
    if provider_id == DeterministicProposalProvider.provider_id:
        return "deterministic_core"
    return "llm"


def validate_proposal(proposal: object, *, expected_agent_id: str, provenance_type: str) -> dict:
    """Validate untrusted provider output before deterministic arbitration."""
    if provenance_type not in ALLOWED_PROVENANCE_TYPES:
        raise ValueError("provenance_type is outside the allowlist")
    if not isinstance(proposal, dict):
        raise ValueError("proposal schema differs from the allowlist")
    keys = set(proposal)
    if not REQUIRED_PROPOSAL_KEYS.issubset(keys) or keys - REQUIRED_PROPOSAL_KEYS - OPTIONAL_PROPOSAL_KEYS:
        raise ValueError("proposal schema differs from the allowlist")
    if proposal["agent_id"] != expected_agent_id:
        raise ValueError("proposal agent_id differs from the requested agent")
    if not isinstance(proposal["action_id"], str):
        raise ValueError("proposal action_id must be a string")
    get_action(proposal["action_id"])
    if type(proposal["priority"]) is not int or not 0 <= proposal["priority"] <= 100:
        raise ValueError("proposal priority must be an integer in 0..100")
    if not isinstance(proposal["rationale"], str) or not proposal["rationale"] or len(proposal["rationale"]) > 500:
        raise ValueError("proposal rationale must be a non-empty bounded string")
    # Ignore any self-declared provenance_type from the provider payload.
    return {
        "agent_id": proposal["agent_id"],
        "action_id": proposal["action_id"],
        "priority": proposal["priority"],
        "rationale": proposal["rationale"],
        "provenance_type": provenance_type,
    }
