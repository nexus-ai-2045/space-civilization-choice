"""Annual local PDCA simulation with deterministic peer interaction."""

from __future__ import annotations

from copy import deepcopy
from typing import Callable
import hashlib

from .action_catalog import get_action
from .agents import AGENT_IDS, AGENT_PREFERENCES
from .parameter_registry import validate_parameters
from .providers import (
    DeterministicProposalProvider,
    derive_provenance_type,
    validate_proposal,
)
from .simulation import ROUNDS, sha256_json
from .trace_v2 import append_trace

THREE_PHASE_CHAIN = ("cognitive_cultural", "economic_organizational", "physical_material", "cognitive_cultural")
ADAPTIVE_YEARS = tuple(range(2026, 2041))
ANNUAL_EFFECT_NUMERATOR = 4
ANNUAL_EFFECT_DENOMINATOR = len(ADAPTIVE_YEARS)

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


def _execution_record_id(year: int, index: int) -> str:
    return f"{year}-E{index:02d}"


def _validate_execution_contract(records: list[dict], saturations: list[dict]) -> None:
    diagnostic_rule_by_kind = {
        "action": "BOUND-ACTION",
        "action_reconciliation": "BOUND-ACTION",
        "feedback": "BOUND-FEEDBACK",
        "uncertainty": "BOUND-UNCERTAINTY",
    }
    record_ids = [record.get("execution_record_id") for record in records]
    if any(not isinstance(record_id, str) or not record_id for record_id in record_ids):
        raise ValueError("execution record ID is missing")
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("execution record IDs must be unique within a round")
    if any(
        set(item) != {"rule_id", "execution_record_id"}
        for item in saturations
    ):
        raise ValueError("saturation diagnostic must only reference an execution record")
    references = [item.get("execution_record_id") for item in saturations]
    if any(reference not in set(record_ids) for reference in references):
        raise ValueError("saturation diagnostic has a dangling execution record ID")
    if len(references) != len(set(references)):
        raise ValueError("execution record has duplicate saturation diagnostics")
    clamped_ids = {
        record["execution_record_id"]
        for record in records
        if record["attempted_delta"] != record["applied_delta"]
    }
    if set(references) != clamped_ids:
        raise ValueError("execution clamp diagnostics are incomplete")
    records_by_id = {record["execution_record_id"]: record for record in records}
    for diagnostic in saturations:
        record = records_by_id[diagnostic["execution_record_id"]]
        expected_rule = diagnostic_rule_by_kind.get(record.get("kind"))
        if expected_rule is None or diagnostic["rule_id"] != expected_rule:
            raise ValueError("saturation diagnostic rule does not match execution kind")


def _truncate_toward_zero(numerator: int, denominator: int) -> int:
    return numerator // denominator if numerator >= 0 else -((-numerator) // denominator)


def _apply_actions(
    axes: dict[str, int], accepted: list[dict], year: int,
    carry: dict[tuple[str, str, str], int],
    *,
    reconcile: bool = False,
) -> tuple[dict[str, int], list[dict], list[dict]]:
    result = deepcopy(axes)
    saturations = []
    records = []
    for item in accepted:
        for axis, delta in item["effects"].items():
            before = result[axis]
            carry_key = (item["agent_id"], item["action_id"], axis)
            carry_before = carry.get(carry_key, 0)
            numerator = delta * ANNUAL_EFFECT_NUMERATOR + carry_before
            annual_delta = _truncate_toward_zero(numerator, ANNUAL_EFFECT_DENOMINATOR)
            carry[carry_key] = numerator - annual_delta * ANNUAL_EFFECT_DENOMINATOR
            result[axis], saturated = _bounded_transition(before + annual_delta)
            records.append(
                {
                    "execution_record_id": _execution_record_id(
                        year, len(records) + 1
                    ),
                    "kind": "action",
                    "year": year,
                    "agent_id": item["agent_id"],
                    "action_id": item["action_id"],
                    "axis": axis,
                    "attempted_delta": annual_delta,
                    "applied_delta": result[axis] - before,
                    "base_delta": delta,
                    "carry_before": carry_before,
                    "carry_after": carry[carry_key],
                }
            )
            if saturated:
                saturations.append(
                    {
                        "rule_id": "BOUND-ACTION",
                        "execution_record_id": records[-1]["execution_record_id"],
                    }
                )
    if reconcile:
        result, reconciliation_saturations, reconciliation_records = (
            _reconcile_action_carries(result, carry, year, len(records) + 1)
        )
        saturations.extend(reconciliation_saturations)
        records.extend(reconciliation_records)
    # Close the three-phase loop: visible outcomes feed legitimacy in every round.
    physical_signal = result["access_and_operation"] - axes["access_and_operation"]
    organizational_signal = result["industrial_reproduction"] - axes["industrial_reproduction"]
    before_legitimacy = result["public_legitimacy"]
    feedback_key = ("__core__", "FEEDBACK-LEGITIMACY", "public_legitimacy")
    feedback_carry_before = carry.get(feedback_key, 0)
    feedback_numerator = physical_signal + organizational_signal + feedback_carry_before
    attempted_delta = _truncate_toward_zero(feedback_numerator, 3)
    carry[feedback_key] = feedback_numerator - attempted_delta * 3
    result["public_legitimacy"], saturated = _bounded_transition(before_legitimacy + attempted_delta)
    records.append(
        {
            "execution_record_id": _execution_record_id(year, len(records) + 1),
            "kind": "feedback",
            "year": year,
            "rule_id": "FEEDBACK-LEGITIMACY",
            "axis": "public_legitimacy",
            "attempted_delta": attempted_delta,
            "applied_delta": result["public_legitimacy"] - before_legitimacy,
            "carry_before": feedback_carry_before,
            "carry_after": carry[feedback_key],
        }
    )
    if saturated:
        saturations.append(
            {
                "rule_id": "BOUND-FEEDBACK",
                "execution_record_id": records[-1]["execution_record_id"],
            }
        )
    return result, saturations, records


def _reconcile_action_carries(
    axes: dict[str, int],
    carry: dict[tuple[str, str, str], int],
    year: int,
    start_index: int,
) -> tuple[dict[str, int], list[dict], list[dict]]:
    """Settle cross-action annualization remainders without losing attribution."""
    result = deepcopy(axes)
    records: list[dict] = []
    saturations: list[dict] = []
    action_keys = [key for key in carry if key[0] != "__core__"]
    for axis in sorted({key[2] for key in action_keys}):
        keys = sorted(key for key in action_keys if key[2] == axis)
        carry_before = sum(carry[key] for key in keys)
        attempted_delta = _truncate_toward_zero(
            carry_before, ANNUAL_EFFECT_DENOMINATOR
        )
        if attempted_delta == 0:
            continue

        units_to_consume = abs(attempted_delta) * ANNUAL_EFFECT_DENOMINATOR
        direction = 1 if attempted_delta > 0 else -1
        contributors = []
        for key in keys:
            available = carry[key] * direction
            if available <= 0 or units_to_consume == 0:
                continue
            consumed = min(available, units_to_consume)
            carry[key] -= direction * consumed
            units_to_consume -= consumed
            contributors.append(
                {
                    "agent_id": key[0],
                    "action_id": key[1],
                    "carry_units_consumed": direction * consumed,
                }
            )
        if units_to_consume:
            raise ValueError("action carry reconciliation could not consume target")

        before = result[axis]
        result[axis], saturated = _bounded_transition(before + attempted_delta)
        record = {
            "execution_record_id": _execution_record_id(
                year, start_index + len(records)
            ),
            "kind": "action_reconciliation",
            "year": year,
            "agent_id": "__aggregate__",
            "action_id": "ANNUAL-ACTION-CARRY-RECONCILIATION",
            "rule_id": "ANNUAL-ACTION-CARRY-RECONCILIATION",
            "axis": axis,
            "attempted_delta": attempted_delta,
            "applied_delta": result[axis] - before,
            "carry_before": carry_before,
            "carry_after": sum(carry[key] for key in keys),
            "contributors": contributors,
        }
        records.append(record)
        if saturated:
            saturations.append(
                {
                    "rule_id": "BOUND-ACTION",
                    "execution_record_id": record["execution_record_id"],
                }
            )

    return result, saturations, records


def _apply_uncertainty(
    axes: dict[str, int], parameters: dict[str, int], year: int, start_index: int,
    carry: dict[str, int],
) -> tuple[dict[str, int], list[dict], list[dict]]:
    """Three bounded external uncertainties produce explicit, traceable shocks."""
    result = deepcopy(axes)
    rules = (
        ("launch_cost_pressure", "access_and_operation", "U-LAUNCH"),
        ("supply_disruption", "industrial_reproduction", "U-SUPPLY"),
        ("international_friction", "relationship_choice", "U-FRICTION"),
    )
    events = []
    records = []
    saturations = []
    for parameter_id, axis, rule_id in rules:
        severity = parameters[parameter_id]
        carry_before = carry[parameter_id]
        legacy_total = -sum(
            (severity * round_index) // 125
            for round_index in range(1, len(ROUNDS) + 1)
        )
        numerator = legacy_total + carry_before
        delta = _truncate_toward_zero(numerator, len(ADAPTIVE_YEARS))
        carry[parameter_id] = numerator - delta * len(ADAPTIVE_YEARS)
        before = result[axis]
        result[axis], saturated = _bounded_transition(before + delta)
        events.append({"parameter_id": parameter_id, "axis": axis, "delta": result[axis] - before, "attempted_delta": delta, "saturated": saturated, "rule_id": rule_id})
        records.append(
            {
                "execution_record_id": _execution_record_id(
                    year, start_index + len(records)
                ),
                "kind": "uncertainty",
                "year": year,
                "parameter_id": parameter_id,
                "rule_id": rule_id,
                "axis": axis,
                "attempted_delta": delta,
                "applied_delta": result[axis] - before,
                "carry_before": carry_before,
                "carry_after": carry[parameter_id],
            }
        )
        if saturated:
            saturations.append(
                {
                    "rule_id": "BOUND-UNCERTAINTY",
                    "execution_record_id": records[-1]["execution_record_id"],
                }
            )
    return result, events, records, saturations


def _peer_responses(proposals: list[dict], *, year: int, seed: int) -> list[dict]:
    """Create one bounded, deterministic response per agent to the next peer."""
    by_agent = {proposal["agent_id"]: proposal for proposal in proposals}
    responses = []
    stances = ("support", "oppose", "amend")
    for index, responder in enumerate(AGENT_IDS):
        target = AGENT_IDS[(index + 1) % len(AGENT_IDS)]
        target_proposal = by_agent[target]
        digest = hashlib.sha256(
            f"{seed}:{year}:{responder}:{target}:{target_proposal['action_id']}".encode()
        ).hexdigest()
        stance = stances[int(digest[:8], 16) % len(stances)]
        responses.append(
            {
                "response_id": f"{year}-R{index + 1:02d}",
                "responder_agent_id": responder,
                "target_agent_id": target,
                "target_action_id": target_proposal["action_id"],
                "stance": stance,
                "priority_delta": {"support": -1, "oppose": 1, "amend": 0}[stance],
                "rationale": f"deterministic peer {stance} response",
            }
        )
    return responses


def _repropose(initial: list[dict], responses: list[dict]) -> list[dict]:
    incoming = {response["target_agent_id"]: response for response in responses}
    reproposals = []
    for proposal in initial:
        response = incoming[proposal["agent_id"]]
        action_id = proposal["action_id"]
        if response["stance"] == "amend":
            choices = AGENT_PREFERENCES[proposal["agent_id"]]
            action_id = choices[(choices.index(action_id) + 1) % len(choices)]
        reproposals.append(
            {
                **proposal,
                "action_id": action_id,
                "priority": min(100, max(0, proposal["priority"] + response["priority_delta"])),
                "rationale": f"{proposal['rationale']}; peer response={response['stance']}",
                "response_id": response["response_id"],
            }
        )
    return reproposals


def run_adaptive_simulation(
    parameters: dict[str, int],
    *,
    seed: int,
    provider: object | None = None,
    provider_timeout_seconds: float | None = None,
    progress_callback: Callable[[dict], None] | None = None,
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
    action_carry: dict[tuple[str, str, str], int] = {}
    uncertainty_carry = {
        key: 0 for key in ("launch_cost_pressure", "supply_disruption", "international_friction")
    }
    trace: list[dict] = []
    rounds = []
    for year in ADAPTIVE_YEARS:
        if progress_callback is not None:
            progress_callback({"event": "year_started", "year": year})
        before = deepcopy(axes)
        initial_proposals = []
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
            initial_proposals.append(proposal)
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
        responses = _peer_responses(initial_proposals, year=year, seed=seed)
        proposals = _repropose(initial_proposals, responses)
        interaction_audit = {
            "initial_proposals_hash": sha256_json(initial_proposals),
            "responses_hash": sha256_json(responses),
            "reproposals_hash": sha256_json(proposals),
        }
        if progress_callback is not None:
            progress_callback({"event": "interaction_completed", "year": year, **interaction_audit})
        resources = _available_resources(checked)
        accepted, used = _arbitrate(proposals, resources)
        axes, transition_saturations, action_records = _apply_actions(
            axes,
            accepted,
            year,
            action_carry,
            reconcile=year == ADAPTIVE_YEARS[-1],
        )
        (
            axes,
            uncertainty_events,
            uncertainty_records,
            uncertainty_saturations,
        ) = _apply_uncertainty(
            axes, checked, year, len(action_records) + 1, uncertainty_carry
        )
        transition_saturations.extend(uncertainty_saturations)
        execution_records = action_records + uncertainty_records
        _validate_execution_contract(execution_records, transition_saturations)
        item = {
            "year": year, "pdca": ["plan", "do", "check", "act"], "before": before,
            "initial_proposals": initial_proposals, "responses": responses,
            "reproposals": proposals, "proposals": proposals,
            "interaction_audit": interaction_audit,
            "accepted_actions": accepted, "resources_available": resources,
            "resources_used": used, "after": deepcopy(axes), "chain_id": "cognition-organization-space-feedback-v1",
            "uncertainty_events": uncertainty_events, "transition_saturations": transition_saturations,
            "execution_records": execution_records,
            "provider_errors": provider_errors,
            "provider_audit": provider_audit,
        }
        rounds.append(item)
        append_trace(trace, item)
        if progress_callback is not None:
            progress_callback({"event": "year_completed", "year": year, "round": len(rounds)})
    result = {
        "model_version": "adaptive-local-v3", "seed": seed, "parameters": checked,
        "three_phase_chain": list(THREE_PHASE_CHAIN), "rounds": rounds, "final_axes": axes, "trace": trace,
        "provider_manifest": provider_identity,
    }
    result["canonical_output_hash"] = sha256_json(result)
    if progress_callback is not None:
        progress_callback({
            "event": "simulation_completed", "year": ADAPTIVE_YEARS[-1],
            "canonical_output_hash": result["canonical_output_hash"],
        })
    return result
