from copy import deepcopy

import pytest

from space_civilization.adaptive_loop import (
    _apply_actions,
    _validate_execution_contract,
    run_adaptive_simulation,
)
from space_civilization.parameter_registry import expand_preset
from space_civilization.providers import DeterministicProposalProvider, derive_provenance_type
from space_civilization.simulation import ROUNDS


class ExternalPythonProvider:
    provider_id = "deterministic_local_v1"

    def propose(self, **kwargs):
        raise AssertionError("closed MVP core must never execute external objects")


def test_five_agents_interact_each_year_from_2026_through_2040():
    assert ROUNDS == (2026, 2030, 2035, 2040)
    result = run_adaptive_simulation(expand_preset("balanced"), seed=42)
    assert len(result["rounds"]) == 15
    assert all(len(item["proposals"]) == 5 for item in result["rounds"])
    assert all(len(item["initial_proposals"]) == 5 for item in result["rounds"])
    assert all(len(item["responses"]) == 5 for item in result["rounds"])
    assert all(len(item["reproposals"]) == 5 for item in result["rounds"])
    assert [item["year"] for item in result["rounds"]] == list(range(2026, 2041))
    assert all(item["proposals"] == item["reproposals"] for item in result["rounds"])
    assert all(
        response["responder_agent_id"] != response["target_agent_id"]
        for item in result["rounds"]
        for response in item["responses"]
    )
    assert all(item["pdca"] == ["plan", "do", "check", "act"] for item in result["rounds"])
    assert result["three_phase_chain"] == ["cognitive_cultural", "economic_organizational", "physical_material", "cognitive_cultural"]


def test_annualized_action_effects_do_not_prematurely_saturate_axes():
    result = run_adaptive_simulation(expand_preset("balanced"), seed=42)
    assert all(0 < value < 100 for value in result["final_axes"].values())
    assert any(
        record["kind"] == "action" and record["carry_after"] != 0
        for item in result["rounds"]
        for record in item["execution_records"]
    )


def test_action_carry_is_scoped_to_agent_action_and_axis_for_trace_attribution():
    axes = {
        "access_and_operation": 50,
        "industrial_reproduction": 50,
        "rule_shaping": 50,
        "knowledge_continuity": 50,
        "relationship_optionality": 50,
        "public_legitimacy": 50,
    }
    carry = {}
    accepted = [
        {"agent_id": "agent-a", "action_id": "action-a", "effects": {"access_and_operation": 2}},
        {"agent_id": "agent-b", "action_id": "action-b", "effects": {"access_and_operation": 2}},
    ]
    _, _, records = _apply_actions(axes, accepted, 2026, carry)
    action_records = [record for record in records if record["kind"] == "action"]
    assert [record["carry_before"] for record in action_records] == [0, 0]
    assert set(carry) == {
        ("agent-a", "action-a", "access_and_operation"),
        ("agent-b", "action-b", "access_and_operation"),
        ("__core__", "FEEDBACK-LEGITIMACY", "public_legitimacy"),
    }


def test_feedback_carry_preserves_annualized_three_phase_remainders():
    axes = {
        "access_and_operation": 50,
        "industrial_reproduction": 50,
        "rule_shaping": 50,
        "knowledge_continuity": 50,
        "relationship_optionality": 50,
        "public_legitimacy": 50,
    }
    carry = {}
    accepted = [{
        "agent_id": "agent-a",
        "action_id": "action-a",
        "effects": {"access_and_operation": 4, "industrial_reproduction": 4},
    }]
    first, _, first_records = _apply_actions(axes, accepted, 2026, carry)
    second, _, second_records = _apply_actions(first, accepted, 2027, carry)
    first_feedback = next(record for record in first_records if record["kind"] == "feedback")
    second_feedback = next(record for record in second_records if record["kind"] == "feedback")
    assert first_feedback["carry_after"] == 2
    assert second_feedback["carry_before"] == 2
    assert first_feedback["attempted_delta"] + second_feedback["attempted_delta"] == 1


def test_progress_events_are_ordered_and_end_with_completion():
    events = []
    result = run_adaptive_simulation(
        expand_preset("balanced"), seed=42, progress_callback=events.append
    )
    assert events[0] == {"event": "year_started", "year": 2026}
    assert events[-1] == {
        "event": "simulation_completed",
        "year": 2040,
        "canonical_output_hash": result["canonical_output_hash"],
    }
    assert [event["year"] for event in events if event["event"] == "year_completed"] == list(range(2026, 2041))


def test_replay_is_deterministic_and_seed_changes_run():
    params = expand_preset("domestic")
    left = run_adaptive_simulation(params, seed=7)
    right = run_adaptive_simulation(params, seed=7, provider=DeterministicProposalProvider())
    other = run_adaptive_simulation(params, seed=8)
    assert left["canonical_output_hash"] == right["canonical_output_hash"]
    assert left["canonical_output_hash"] != other["canonical_output_hash"]


def test_arbiter_never_spends_more_than_round_resources():
    result = run_adaptive_simulation(expand_preset("balanced"), seed=3)
    for item in result["rounds"]:
        assert all(
            item["resources_used"][key] <= item["resources_available"][key]
            for key in item["resources_available"]
        )
        assert item["accepted_actions"] == sorted(
            item["accepted_actions"],
            key=lambda proposal: (
                proposal["priority"],
                proposal["agent_id"],
                proposal["action_id"],
            ),
        )


def test_external_uncertainties_are_applied_and_traced_each_round():
    result = run_adaptive_simulation(expand_preset("international"), seed=4)
    assert all(len(item["uncertainty_events"]) == 3 for item in result["rounds"])
    assert all(
        event["rule_id"].startswith("U-")
        for item in result["rounds"]
        for event in item["uncertainty_events"]
    )


def test_execution_records_are_emitted_at_transition_point_and_reconcile_after():
    result = run_adaptive_simulation(expand_preset("balanced"), seed=4)
    for round_item in result["rounds"]:
        cursor = dict(round_item["before"])
        kinds = [record["kind"] for record in round_item["execution_records"]]
        record_ids = [
            record["execution_record_id"]
            for record in round_item["execution_records"]
        ]
        assert len(record_ids) == len(set(record_ids))
        assert record_ids == [
            f'{round_item["year"]}-E{index:02d}'
            for index in range(1, len(record_ids) + 1)
        ]
        assert kinds.count("feedback") == 1
        assert kinds.count("uncertainty") == 3
        assert "saturation" not in kinds
        for record in round_item["execution_records"]:
            cursor[record["axis"]] += record["applied_delta"]
        assert cursor == round_item["after"]


def test_execution_record_contract_covers_uncertainty_identity_and_all_clamps():
    parameters = expand_preset("balanced")
    allocation_ids = (
        "transport", "autonomy", "life_support", "energy", "domestic_supply",
        "people_research", "international_connection", "open_platform",
    )
    for key in allocation_ids:
        parameters[key] = 0
    parameters["domestic_supply"] = 100
    parameters.update(
        {
            "technology_readiness": 0,
            "industrial_capacity": 0,
            "domestic_procurement": 100,
            "dependency_tolerance": 0,
            "launch_cost_pressure": 100,
            "supply_disruption": 100,
            "international_friction": 100,
        }
    )
    result = run_adaptive_simulation(parameters, seed=4)
    clamped_uncertainty_seen = False
    for round_item in result["rounds"]:
        uncertainty_records = [
            record for record in round_item["execution_records"]
            if record["kind"] == "uncertainty"
        ]
        assert {record["parameter_id"] for record in uncertainty_records} == {
            "launch_cost_pressure", "supply_disruption", "international_friction"
        }
        for record in round_item["execution_records"]:
            if record["attempted_delta"] == record["applied_delta"]:
                continue
            matches = [
                diagnostic for diagnostic in round_item["transition_saturations"]
                if diagnostic["execution_record_id"]
                == record["execution_record_id"]
            ]
            assert matches
            assert set(matches[0]) == {"rule_id", "execution_record_id"}
            if record["kind"] == "uncertainty":
                clamped_uncertainty_seen = True
    assert clamped_uncertainty_seen


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_id",
        "duplicate_id",
        "dangling",
        "missing_diagnostic",
        "unclamped_diagnostic",
        "wrong_diagnostic_kind",
    ),
)
def test_execution_record_reference_contract_rejects_invalid_graph(mutation):
    records = [
        {
            "execution_record_id": "2026-E01",
            "kind": "uncertainty",
            "attempted_delta": -3,
            "applied_delta": -1,
        },
        {
            "execution_record_id": "2026-E02",
            "kind": "action",
            "attempted_delta": 1,
            "applied_delta": 1,
        },
    ]
    diagnostics = [
        {"rule_id": "BOUND-UNCERTAINTY", "execution_record_id": "2026-E01"}
    ]
    records = deepcopy(records)
    diagnostics = deepcopy(diagnostics)
    if mutation == "missing_id":
        records[0].pop("execution_record_id")
    elif mutation == "duplicate_id":
        records[1]["execution_record_id"] = "2026-E01"
    elif mutation == "dangling":
        diagnostics[0]["execution_record_id"] = "2026-E99"
    elif mutation == "missing_diagnostic":
        diagnostics.clear()
    elif mutation == "unclamped_diagnostic":
        diagnostics.append(
            {"rule_id": "BOUND-ACTION", "execution_record_id": "2026-E02"}
        )
    else:
        diagnostics[0]["rule_id"] = "BOUND-ACTION"
    with pytest.raises(ValueError):
        _validate_execution_contract(records, diagnostics)


def test_all_valid_parameter_boundaries_complete_with_explicit_saturation():
    allocation_ids = {
        "transport",
        "autonomy",
        "life_support",
        "energy",
        "domestic_supply",
        "people_research",
        "international_connection",
        "open_platform",
    }
    high = expand_preset("balanced")
    for key in high:
        if key not in allocation_ids:
            high[key] = 100
    low = expand_preset("balanced")
    low["industrial_capacity"] = 0
    low["supply_disruption"] = 100

    for parameters in (high, low):
        result = run_adaptive_simulation(parameters, seed=5)
        assert all(0 <= value <= 100 for value in result["final_axes"].values())
        assert all(
            "saturated" in event
            for item in result["rounds"]
            for event in item["uncertainty_events"]
        )


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


def test_closed_registry_rejects_arbitrary_python_provider_objects():
    with pytest.raises(ValueError, match="future bounded JSON/HTTP adapter"):
        run_adaptive_simulation(
            expand_preset("balanced"), seed=18, provider=ExternalPythonProvider()
        )


def test_exact_builtin_instance_is_not_executed_when_supplied_by_caller():
    supplied = DeterministicProposalProvider()

    def fail_if_called(**_kwargs):
        raise AssertionError("caller-owned provider instance must not execute")

    supplied.propose = fail_if_called
    result = run_adaptive_simulation(
        expand_preset("balanced"), seed=18, provider=supplied
    )
    baseline = run_adaptive_simulation(expand_preset("balanced"), seed=18)
    assert result["canonical_output_hash"] == baseline["canonical_output_hash"]


def test_timeout_option_is_deferred_with_external_adapter():
    with pytest.raises(ValueError, match="future external adapter"):
        run_adaptive_simulation(
            expand_preset("balanced"), seed=19, provider_timeout_seconds=0.1
        )


def test_deterministic_provenance_requires_concrete_builtin_type():
    assert derive_provenance_type(DeterministicProposalProvider()) == "deterministic_core"
    assert derive_provenance_type(ExternalPythonProvider()) == "llm"


def test_manifest_uses_core_owned_provider_identity():
    result = run_adaptive_simulation(expand_preset("balanced"), seed=20)
    assert result["provider_manifest"] == {
        "provider_id": "deterministic_local_v1",
        "model_id": None,
        "model_version": None,
    }
    assert all(
        audit["provider_id"] == "deterministic_local_v1"
        and audit["transport_response_hash"] == audit["validated_response_hash"]
        and audit["fallback_used"] is False
        for item in result["rounds"]
        for audit in item["provider_audit"]
    )
