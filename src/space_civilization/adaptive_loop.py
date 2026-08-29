"""Four-round local PDCA simulation with deterministic arbitration."""

from __future__ import annotations

from copy import deepcopy

from .action_catalog import get_action
from .agents import AGENT_IDS
from .parameter_registry import validate_parameters
from .providers import (
    DeterministicProposalProvider,
    derive_provenance_type,
    validate_proposal,
)
from .simulation import ROUNDS, sha256_json
from .trace_v2 import append_trace

THREE_PHASE_CHAIN = ("cognitive_cultural", "economic_organizational", "physical_material", "cognitive_cultural")

CORE_PROVIDER_REGISTRY = {
    DeterministicProposalProvider.provider_id: DeterministicProposalProvider,
}


def _initial_axes(parameters: dict[str, int]) -> dict[str, int]:
    return {
        "access_and_operation": sum(parameters[key] for key in ("technology_readiness", "transport", "autonomy", "life_support", "energy")) // 5,
        "industrial_reproduction": sum(parameters[key] for key in ("industrial_capacity", "domestic_supply")) // 2,
        "rule_shaping": sum(parameters[key] for key in ("international_connection", "technology_openness", "open_platform")) // 3,
        "knowledge_continuity": sum(parameters[key] for key in ("talent_base", "people_research")) // 2,
        "relationship_choice": (
            100 - parameters["domestic_procurement"]
            + parameters["dependency_tolerance"]
            + parameters["international_connection"]
        ) // 3,
        "public_legitimacy": (
            parameters["public_support"]
            + 100 - parameters["short_term_orientation"]
            + parameters["risk_tolerance"]
        ) // 3,
    }


def _available_resources(parameters: dict[str, int]) -> dict[str, int]:
    return {
        "budget": max(6, sum(parameters[key] for key in ("transport", "domestic_supply", "international_connection")) // 3),
        "people": max(5, parameters["talent_base"] // 5),
        "time": 8,
    }


def _arbitrate(proposals: list[dict], resources: dict[str, int]) -> tuple[list[dict], dict[str, int]]:
    accepted, used = [], {key: 0 for key in resources}
    for proposal in sorted(proposals, key=lambda item: (item["priority"], item["agent_id"], item["action_id"])):
        action = get_action(proposal["action_id"])
        if all(used[key] + action["cost"][key] <= resources[key] for key in resources):
            accepted.append({**proposal, "cost": action["cost"], "effects": action["effects"]})
            for key in resources:
                used[key] += action["cost"][key]
    return accepted, used


def _bounded_transition(value: int) -> tuple[int, bool]:
    bounded = min(100, max(0, value))
    return bounded, bounded != value


def _apply_actions(axes: dict[str, int], accepted: list[dict]) -> tuple[dict[str, int], list[dict]]:
    result = deepcopy(axes)
    saturations = []
    for item in accepted:
        for axis, delta in item["effects"].items():
            before = result[axis]
            result[axis], saturated = _bounded_transition(before + delta)
            if saturated:
                saturations.append({"rule_id": "BOUND-ACTION", "axis": axis, "attempted_delta": delta, "applied_delta": result[axis] - before})
    # Close the three-phase loop: visible outcomes feed legitimacy in every round.
    physical_signal = result["access_and_operation"] - axes["access_and_operation"]
    organizational_signal = result["industrial_reproduction"] - axes["industrial_reproduction"]
    before_legitimacy = result["public_legitimacy"]
    attempted_delta = (physical_signal + organizational_signal) // 3
    result["public_legitimacy"], saturated = _bounded_transition(before_legitimacy + attempted_delta)
    if saturated:
        saturations.append({"rule_id": "BOUND-FEEDBACK", "axis": "public_legitimacy", "attempted_delta": attempted_delta, "applied_delta": result["public_legitimacy"] - before_legitimacy})
    return result, saturations


def _apply_uncertainty(axes: dict[str, int], parameters: dict[str, int], year: int) -> tuple[dict[str, int], list[dict]]:
    """Three bounded external uncertainties produce explicit, traceable shocks."""
    result = deepcopy(axes)
    rules = (
        ("launch_cost_pressure", "access_and_operation", "U-LAUNCH"),
        ("supply_disruption", "industrial_reproduction", "U-SUPPLY"),
        ("international_friction", "relationship_choice", "U-FRICTION"),
    )
    events = []
    round_index = ROUNDS.index(year) + 1
    for parameter_id, axis, rule_id in rules:
        severity = parameters[parameter_id]
        delta = -((severity * round_index) // 125)
        before = result[axis]
        result[axis], saturated = _bounded_transition(before + delta)
        events.append({"parameter_id": parameter_id, "axis": axis, "delta": result[axis] - before, "attempted_delta": delta, "saturated": saturated, "rule_id": rule_id})
    return result, events


def run_adaptive_simulation(
    parameters: dict[str, int],
    *,
    seed: int,
    provider: object | None = None,
    provider_timeout_seconds: float | None = None,
) -> dict:
    if type(seed) is not int:
        raise ValueError("seed must be a strict integer")
    checked = validate_parameters(parameters)
    if provider is not None and type(provider) is not DeterministicProposalProvider:
        raise ValueError(
            "external Python providers are not supported by the MVP core; "
            "use the future bounded JSON/HTTP adapter"
        )
    if provider_timeout_seconds is not None:
        raise ValueError("provider_timeout_seconds belongs to the future external adapter")
    # A compatible caller argument is only a migration marker. Execution authority
    # always comes from a fresh instance of the core-owned registry implementation.
    active_provider = CORE_PROVIDER_REGISTRY[
        DeterministicProposalProvider.provider_id
    ]()
    provider_identity = {
        "provider_id": DeterministicProposalProvider.provider_id,
        "model_id": None,
        "model_version": None,
    }
    provenance_type = derive_provenance_type(active_provider)
    axes = _initial_axes(checked)
    trace: list[dict] = []
    rounds = []
    for year in ROUNDS:
        before = deepcopy(axes)
        proposals = []
        provider_errors = []
        provider_audit = []
        for agent_id in AGENT_IDS:
            # Providers receive isolated copies; core retains ownership of transitions.
            state_view = deepcopy(before)
            parameter_view = deepcopy(checked)
            request_payload = {
                "agent_id": agent_id,
                "year": year,
                "seed": seed,
                "state": state_view,
                "parameters": parameter_view,
            }
            request_hash = sha256_json(request_payload)
            raw_proposal = active_provider.propose(
                agent_id=agent_id,
                year=year,
                seed=seed,
                state=state_view,
                parameters=parameter_view,
            )
            proposal = validate_proposal(
                raw_proposal,
                expected_agent_id=agent_id,
                provenance_type=provenance_type,
            )
            response_hash = sha256_json(proposal)
            proposals.append(proposal)
            provider_audit.append(
                {
                    **provider_identity,
                    "agent_id": agent_id,
                    "request_hash": request_hash,
                    "response_hash": response_hash,
                    "transport_response_hash": response_hash,
                    "validated_response_hash": response_hash,
                    "validation_state": "accepted_for_run",
                    "fallback_used": False,
                }
            )
        resources = _available_resources(checked)
        accepted, used = _arbitrate(proposals, resources)
        axes, transition_saturations = _apply_actions(axes, accepted)
        axes, uncertainty_events = _apply_uncertainty(axes, checked, year)
        item = {
            "year": year, "pdca": ["plan", "do", "check", "act"], "before": before,
            "proposals": proposals, "accepted_actions": accepted, "resources_available": resources,
            "resources_used": used, "after": deepcopy(axes), "chain_id": "cognition-organization-space-feedback-v1",
            "uncertainty_events": uncertainty_events, "transition_saturations": transition_saturations,
            "provider_errors": provider_errors,
            "provider_audit": provider_audit,
        }
        rounds.append(item)
        append_trace(trace, item)
    result = {
        "model_version": "adaptive-local-v2", "seed": seed, "parameters": checked,
        "three_phase_chain": list(THREE_PHASE_CHAIN), "rounds": rounds, "final_axes": axes, "trace": trace,
        "provider_manifest": provider_identity,
    }
    result["canonical_output_hash"] = sha256_json(result)
    return result
