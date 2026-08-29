"""Four-round local PDCA simulation with deterministic arbitration."""

from __future__ import annotations

import multiprocessing
import urllib.error
from copy import deepcopy
from multiprocessing.context import BaseContext
from typing import Any

from .action_catalog import get_action
from .agents import AGENT_IDS
from .parameter_registry import validate_parameters
from .providers import (
    DeterministicProposalProvider,
    ProposalProvider,
    derive_provenance_type,
    validate_proposal,
)
from .simulation import ROUNDS, sha256_json
from .trace_v2 import append_trace

# Fail-closed local fallback: connectivity and schema failures must not abort the run.
_PROVIDER_FALLBACK_ERRORS = (
    KeyError,
    TimeoutError,
    TypeError,
    ValueError,
    ConnectionError,
    OSError,
    urllib.error.URLError,
)

# Core-owned deadline so hanging I/O cannot block the deterministic run.
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 2.0
_PROVIDER_JOIN_GRACE_SECONDS = 0.5

THREE_PHASE_CHAIN = ("cognitive_cultural", "economic_organizational", "physical_material", "cognitive_cultural")

_ERROR_NAME_TO_TYPE: dict[str, type[BaseException]] = {
    "TimeoutError": TimeoutError,
    "ConnectionError": ConnectionError,
    "OSError": OSError,
    "KeyError": KeyError,
    "TypeError": TypeError,
    "ValueError": ValueError,
    "URLError": urllib.error.URLError,
}


def _provider_process_worker(
    provider: ProposalProvider,
    kwargs: dict[str, Any],
    result_queue: multiprocessing.Queue,
) -> None:
    """Isolated worker entrypoint; must stay picklable for spawn contexts."""
    try:
        result_queue.put(("ok", provider.propose(**kwargs)))
    except BaseException as error:  # noqa: BLE001 - resurface exact failure to the core
        result_queue.put(("err", type(error).__name__, str(error)))


def _terminate_provider_process(process: multiprocessing.Process) -> None:
    """Hard-stop a timed-out provider worker so blocked calls cannot linger."""
    if not process.is_alive():
        process.join(timeout=_PROVIDER_JOIN_GRACE_SECONDS)
        return
    process.terminate()
    process.join(timeout=_PROVIDER_JOIN_GRACE_SECONDS)
    if process.is_alive():
        process.kill()
        process.join(timeout=_PROVIDER_JOIN_GRACE_SECONDS)


def _multiprocessing_context() -> BaseContext:
    # spawn avoids inheriting parent threads and keeps the worker boundary isolatable.
    return multiprocessing.get_context("spawn")


def _propose_with_deadline(
    provider: ProposalProvider,
    *,
    timeout_seconds: float,
    agent_id: str,
    year: int,
    seed: int,
    state: dict,
    parameters: dict,
) -> dict:
    """Invoke a provider behind a core-owned deadline; hanging I/O becomes TimeoutError."""
    if timeout_seconds <= 0:
        raise ValueError("provider timeout must be positive")
    # Local deterministic proposals are sync and immediate; skip process hop.
    if getattr(provider, "provider_id", None) == DeterministicProposalProvider.provider_id:
        return provider.propose(
            agent_id=agent_id, year=year, seed=seed, state=state, parameters=parameters
        )

    ctx = _multiprocessing_context()
    result_queue: multiprocessing.Queue = ctx.Queue(maxsize=1)
    kwargs = {
        "agent_id": agent_id,
        "year": year,
        "seed": seed,
        "state": state,
        "parameters": parameters,
    }
    process = ctx.Process(
        target=_provider_process_worker,
        args=(provider, kwargs, result_queue),
        daemon=True,
        name=f"scc-provider-{agent_id}-{year}",
    )
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        _terminate_provider_process(process)
        raise TimeoutError("provider proposal exceeded core-owned deadline")

    process.join(timeout=_PROVIDER_JOIN_GRACE_SECONDS)
    try:
        message = result_queue.get_nowait()
    except Exception as error:
        raise TimeoutError("provider worker exited without a result") from error

    if message[0] == "ok":
        return message[1]

    error_name, error_text = message[1], message[2]
    error_type = _ERROR_NAME_TO_TYPE.get(error_name, ValueError)
    if error_type is urllib.error.URLError:
        raise urllib.error.URLError(error_text)
    raise error_type(error_text)
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
    provider: ProposalProvider | None = None,
    provider_timeout_seconds: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
) -> dict:
    if type(seed) is not int:
        raise ValueError("seed must be a strict integer")
    checked = validate_parameters(parameters)
    active_provider = provider or DeterministicProposalProvider()
    provenance_type = derive_provenance_type(active_provider)
    local_provider = DeterministicProposalProvider()
    local_provenance = derive_provenance_type(local_provider)
    axes = _initial_axes(checked)
    trace: list[dict] = []
    rounds = []
    for year in ROUNDS:
        before = deepcopy(axes)
        proposals = []
        provider_errors = []
        for agent_id in AGENT_IDS:
            # Providers receive isolated copies; core retains ownership of transitions.
            state_view = deepcopy(before)
            parameter_view = deepcopy(checked)
            try:
                proposal = _propose_with_deadline(
                    active_provider,
                    timeout_seconds=provider_timeout_seconds,
                    agent_id=agent_id,
                    year=year,
                    seed=seed,
                    state=state_view,
                    parameters=parameter_view,
                )
                proposals.append(
                    validate_proposal(
                        proposal,
                        expected_agent_id=agent_id,
                        provenance_type=provenance_type,
                    )
                )
            except _PROVIDER_FALLBACK_ERRORS as error:
                fallback = local_provider.propose(
                    agent_id=agent_id,
                    year=year,
                    seed=seed,
                    state=deepcopy(before),
                    parameters=deepcopy(checked),
                )
                proposals.append(
                    validate_proposal(
                        fallback,
                        expected_agent_id=agent_id,
                        provenance_type=local_provenance,
                    )
                )
                provider_errors.append(
                    {
                        "agent_id": agent_id,
                        "error": type(error).__name__,
                        "fallback": "deterministic_local_v1",
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
        }
        rounds.append(item)
        append_trace(trace, item)
    result = {
        "model_version": "adaptive-local-v2", "seed": seed, "parameters": checked,
        "three_phase_chain": list(THREE_PHASE_CHAIN), "rounds": rounds, "final_axes": axes, "trace": trace,
    }
    result["canonical_output_hash"] = sha256_json(result)
    return result
