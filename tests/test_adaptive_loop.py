import urllib.error

from space_civilization.adaptive_loop import run_adaptive_simulation
from space_civilization.parameter_registry import expand_preset
from space_civilization.providers import DeterministicProposalProvider


class InvalidProvider:
    def propose(self, **kwargs):
        return {"agent_id": "forged", "action_id": "not_allowlisted", "priority": -1}


class TimeoutProvider:
    def propose(self, **kwargs):
        raise TimeoutError("provider deadline exceeded")


class ConnectionFailProvider:
    def propose(self, **kwargs):
        raise ConnectionError("provider unreachable")


class UrlErrorProvider:
    def propose(self, **kwargs):
        raise urllib.error.URLError("name or service not known")


class MutatingProvider:
    provider_id = "external_mutator_v1"
    provenance_type = "llm"

    def propose(self, **kwargs):
        kwargs["parameters"]["supply_disruption"] = 99
        kwargs["state"]["public_legitimacy"] = -50
        return {
            "agent_id": kwargs["agent_id"],
            "action_id": "train_people",
            "priority": 0,
            "rationale": "mutates caller inputs",
            "provenance_type": "deterministic_core",
        }


class SpoofedProvenanceProvider:
    provider_id = "external_spoof_v1"

    def propose(self, **kwargs):
        return {
            "agent_id": kwargs["agent_id"],
            "action_id": "train_people",
            "priority": 0,
            "rationale": "claims local provenance",
            "provenance_type": "deterministic_core",
        }


def test_five_agents_repeat_pdca_for_four_rounds():
    result = run_adaptive_simulation(expand_preset("balanced"), seed=42)
    assert len(result["rounds"]) == 4
    assert all(len(item["proposals"]) == 5 for item in result["rounds"])
    assert [item["year"] for item in result["rounds"]] == [2026, 2030, 2035, 2040]
    assert all(item["pdca"] == ["plan", "do", "check", "act"] for item in result["rounds"])
    assert result["three_phase_chain"] == [
        "cognitive_cultural",
        "economic_organizational",
        "physical_material",
        "cognitive_cultural",
    ]


def test_replay_is_deterministic_and_seed_changes_run():
    params = expand_preset("domestic")
    provider = DeterministicProposalProvider()
    left = run_adaptive_simulation(params, seed=7, provider=provider)
    right = run_adaptive_simulation(params, seed=7, provider=provider)
    other = run_adaptive_simulation(params, seed=8, provider=provider)
    assert left["canonical_output_hash"] == right["canonical_output_hash"]
    assert left["canonical_output_hash"] != other["canonical_output_hash"]


def test_arbiter_never_spends_more_than_round_resources():
    result = run_adaptive_simulation(expand_preset("open_platform"), seed=3)
    for round_result in result["rounds"]:
        assert round_result["resources_used"]["budget"] <= round_result["resources_available"]["budget"]
        assert round_result["resources_used"]["people"] <= round_result["resources_available"]["people"]
        assert round_result["resources_used"]["time"] <= round_result["resources_available"]["time"]
        assert round_result["accepted_actions"] == sorted(
            round_result["accepted_actions"], key=lambda item: (item["priority"], item["agent_id"], item["action_id"])
        )


def test_external_uncertainties_are_applied_and_traced_each_round():
    result = run_adaptive_simulation(expand_preset("balanced"), seed=12)

    assert all(len(item["uncertainty_events"]) == 3 for item in result["rounds"])
    assert all(event["rule_id"].startswith("U-") for item in result["rounds"] for event in item["uncertainty_events"])


def test_all_valid_parameter_boundaries_complete_with_explicit_saturation():
    high = expand_preset("balanced")
    for key in high:
        if key not in {"transport", "autonomy", "life_support", "energy", "domestic_supply", "people_research", "international_connection", "open_platform"}:
            high[key] = 100
    low = expand_preset("balanced")
    low["industrial_capacity"] = 0
    low["supply_disruption"] = 100

    for parameters in (high, low):
        result = run_adaptive_simulation(parameters, seed=5)
        assert all(0 <= value <= 100 for value in result["final_axes"].values())
        assert all("saturated" in event for item in result["rounds"] for event in item["uncertainty_events"])


def test_invalid_provider_output_falls_back_to_valid_local_proposals():
    result = run_adaptive_simulation(expand_preset("balanced"), seed=6, provider=InvalidProvider())
    assert all(len(item["provider_errors"]) == 5 for item in result["rounds"])
    assert all(proposal["provenance_type"] == "deterministic_core" for item in result["rounds"] for proposal in item["proposals"])


def test_provider_timeout_falls_back_and_all_rounds_complete():
    result = run_adaptive_simulation(expand_preset("balanced"), seed=6, provider=TimeoutProvider())
    assert len(result["rounds"]) == 4
    assert all(len(item["provider_errors"]) == 5 for item in result["rounds"])
    assert {error["error"] for item in result["rounds"] for error in item["provider_errors"]} == {"TimeoutError"}


def test_provider_connection_loss_falls_back_and_all_rounds_complete():
    for provider, error_name in (
        (ConnectionFailProvider(), "ConnectionError"),
        (UrlErrorProvider(), "URLError"),
    ):
        result = run_adaptive_simulation(expand_preset("balanced"), seed=6, provider=provider)
        assert len(result["rounds"]) == 4
        assert all(len(item["provider_errors"]) == 5 for item in result["rounds"])
        assert {error["error"] for item in result["rounds"] for error in item["provider_errors"]} == {error_name}
        assert all(
            proposal["provenance_type"] == "deterministic_core"
            for item in result["rounds"]
            for proposal in item["proposals"]
        )


def test_provider_cannot_mutate_core_owned_state_or_parameters():
    params = expand_preset("balanced")
    baseline = params["supply_disruption"]
    result = run_adaptive_simulation(params, seed=11, provider=MutatingProvider())
    assert params["supply_disruption"] == baseline
    assert result["parameters"]["supply_disruption"] == baseline
    assert all(item["before"]["public_legitimacy"] >= 0 for item in result["rounds"])
    assert all(proposal["provenance_type"] == "llm" for item in result["rounds"] for proposal in item["proposals"])


def test_provenance_is_derived_from_provider_identity_not_payload():
    result = run_adaptive_simulation(expand_preset("balanced"), seed=11, provider=SpoofedProvenanceProvider())
    assert all(proposal["provenance_type"] == "llm" for item in result["rounds"] for proposal in item["proposals"])
    assert all(not item["provider_errors"] for item in result["rounds"])


def test_every_parameter_changes_model_state_or_uncertainty_trace():
    baseline = expand_preset("balanced")
    baseline_result = run_adaptive_simulation(baseline, seed=17)
    allocation_ids = ("transport", "autonomy", "life_support", "energy", "domestic_supply", "people_research", "international_connection", "open_platform")
    for key in baseline:
        changed = dict(baseline)
        if key in allocation_ids:
            donor = "transport" if key == "domestic_supply" else "domestic_supply"
            changed[key] += 10
            changed[donor] -= 10
        else:
            changed[key] = 0 if changed[key] != 0 else 100
        result = run_adaptive_simulation(changed, seed=17)
        assert (
            result["final_axes"] != baseline_result["final_axes"]
            or [item["uncertainty_events"] for item in result["rounds"]]
            != [item["uncertainty_events"] for item in baseline_result["rounds"]]
        ), key
