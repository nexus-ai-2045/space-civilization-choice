from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_civilization import (
    SimulationError,
    common_scenario_snapshot,
    deterministic_execution_input_hash,
    load_fixture,
    run_simulation,
    sha256_json,
)

FIXTURE = ROOT / "fixtures/phase1_domestic_autonomy.json"


def test_same_fixture_replays_to_same_hash_and_event_log():
    first = run_simulation(load_fixture(FIXTURE))
    second = run_simulation(load_fixture(FIXTURE))

    assert first == second
    assert first["manifest"]["scenario_snapshot_hash"] == second["manifest"]["scenario_snapshot_hash"]
    assert first["canonical_output_hash"] == second["canonical_output_hash"]
    assert first["event_log_hash"] == second["event_log_hash"]
    assert len(first["events"]) == 4


def test_different_seed_changes_seeded_exogenous_stream_and_event_log():
    first_fixture = load_fixture(FIXTURE)
    second_fixture = load_fixture(FIXTURE)
    second_fixture["seed"] += 1

    first = run_simulation(first_fixture)
    second = run_simulation(second_fixture)

    assert first["manifest"]["exogenous_event_stream_hash"] != second["manifest"]["exogenous_event_stream_hash"]
    assert first["event_log_hash"] != second["event_log_hash"]
    assert first["final_state"] != second["final_state"]


@pytest.mark.parametrize(
    ("mutator", "hash_must_change"),
    [
        (
            lambda fixture: (
                fixture["rounds"][0].__setitem__(
                    "action", "qualify_redundant_component_supply"
                ),
                    fixture["rounds"][0].__setitem__("rule_id", "R-DOM-02"),
                    fixture["rounds"][0].__setitem__(
                        "axis_deltas",
                        {
                            "access_and_operation": 3,
                            "industrial_reproduction": 7,
                            "rule_shaping": 0,
                            "knowledge_continuity": 2,
                            "relationship_choice": 1,
                            "public_legitimacy": 1,
                        },
                    ),
            ),
            False,
        ),
        (
            lambda fixture: fixture["rounds"][0].__setitem__(
                "exogenous_event", "single_supplier_disruption"
            ),
            True,
        ),
        (
                lambda fixture: fixture["rounds"][0].__setitem__(
                    "actor", "research_and_next_generation_alliance"
                ),
            False,
        ),
    ],
)
def test_scenario_snapshot_hash_binds_shared_inputs_only(mutator, hash_must_change):
    first_fixture = load_fixture(FIXTURE)
    second_fixture = load_fixture(FIXTURE)
    mutator(second_fixture)

    first = run_simulation(first_fixture)
    second = run_simulation(second_fixture)

    if hash_must_change:
        assert first["manifest"]["scenario_snapshot_hash"] != second["manifest"]["scenario_snapshot_hash"]
    else:
        assert first["manifest"]["scenario_snapshot_hash"] == second["manifest"]["scenario_snapshot_hash"]
        assert first["event_log_hash"] != second["event_log_hash"]
        assert first["manifest"]["deterministic_execution_input_hash"] != second["manifest"][
            "deterministic_execution_input_hash"
        ]


def test_common_scenario_snapshot_excludes_branch_specific_fields():
    first = load_fixture(FIXTURE)
    second = load_fixture(FIXTURE)
    second["branch"] = "open_platform"
    second["rounds"][0]["action"] = "qualify_redundant_component_supply"
    second["rounds"][0]["actor"] = "research_and_next_generation_alliance"
    second["rounds"][0]["rule_id"] = "R-OTHER-01"
    second["rounds"][0]["evidence_ref"] = "model-assumption:other"

    assert sha256_json(common_scenario_snapshot(first)) == sha256_json(
        common_scenario_snapshot(second)
    )
    assert sha256_json(first) != sha256_json(second)


def test_deterministic_execution_input_hash_recomputes_from_fixture_content():
    first = load_fixture(FIXTURE)
    second = load_fixture(FIXTURE)
    second["rounds"][0]["axis_deltas"]["industrial_reproduction"] += 1

    assert deterministic_execution_input_hash(first) == sha256_json(first)
    assert deterministic_execution_input_hash(first) != deterministic_execution_input_hash(second)


@pytest.mark.parametrize("branch", ["international_integration", "open_platform"])
def test_phase1_rejects_branches_without_transition_rules(branch):
    data = load_fixture(FIXTURE)
    data["branch"] = branch

    with pytest.raises(SimulationError, match="domestic_autonomy"):
        run_simulation(data)


def test_every_axis_delta_traces_to_a_turn_rule_and_evidence_model_internal():
    result = run_simulation(load_fixture(FIXTURE))

    assert len(result["trace"]) == 4
    for expected_turn, event in enumerate(result["events"], start=1):
        assert event["turn_id"] == expected_turn
        assert event["rule_id"].startswith("R-DOM-")
        assert event["evidence_ref"].startswith("model-assumption:")
        assert event["record_kind"] == "simulated_transition"
        assert event["epistemic_class"] == "model_assumption"
        assert event["provenance_type"] == "deterministic_core"
        assert event["validation_state"] == "accepted_for_run"
        assert set(event["axis_deltas"]) == set(event["before"]) == set(event["after"])
        for axis in event["before"]:
            assert event["before"][axis] + event["axis_deltas"][axis] == event["after"][axis]
        trace = result["trace"][expected_turn - 1]
        assert trace["turn_id"] == expected_turn
        assert trace["inputs"] == event["input"]
        assert trace["action"] == event["action"]
        assert trace["model_rule"] == event["rule_id"]
        assert trace["evidence_refs"] == [event["evidence_ref"]]
        assert trace["causal_scope"] == "model_internal"
        assert trace["axis_deltas"] == event["axis_deltas"]
        assert trace["base_axis_deltas"] == event["base_axis_deltas"]
        assert trace["exogenous_effect"] == event["exogenous_effect"]
        assert trace["exogenous_effect"]["provenance"] == event["input"]["exogenous_event"]
        assert trace["random_draw"] == event["random_draw"]


def test_result_deep_copies_fixture_base_axis_deltas():
    fixture = load_fixture(FIXTURE)
    result = run_simulation(fixture)
    recorded = result["events"][0]["base_axis_deltas"].copy()

    fixture["rounds"][0]["axis_deltas"]["access_and_operation"] += 99

    assert result["events"][0]["base_axis_deltas"] == recorded


def test_fixture_rejects_missing_agent_or_invalid_rounds(tmp_path):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["initial_state"]["agents"].pop("international_partners")
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(SimulationError, match="five canonical agents"):
        load_fixture(invalid)


@pytest.mark.parametrize("actor", [None, "not_an_agent"])
def test_fixture_rejects_missing_or_unknown_round_actor(actor):
    data = load_fixture(FIXTURE)
    data["rounds"][0]["actor"] = actor

    with pytest.raises(SimulationError, match="canonical agent"):
        run_simulation(data)


def test_fixture_rejects_missing_exogenous_event():
    data = load_fixture(FIXTURE)
    data["rounds"][0].pop("exogenous_event")

    with pytest.raises(SimulationError, match="exogenous_event"):
        run_simulation(data)


def test_fixture_rejects_unknown_action():
    data = load_fixture(FIXTURE)
    data["rounds"][0]["action"] = "launch_attack"

    with pytest.raises(SimulationError, match="Phase 1 allowed action"):
        run_simulation(data)


def test_fixture_rejects_action_rule_or_base_delta_mismatch():
    data = load_fixture(FIXTURE)
    data["rounds"][0]["action"] = "operate_with_domestic_maintenance_chain"
    # Keep R-DOM-01 from the original turn-1 fixture while swapping the action.
    data["rounds"][0]["rule_id"] = "R-DOM-01"

    with pytest.raises(SimulationError, match="does not match transition rule"):
        run_simulation(data)

    data = load_fixture(FIXTURE)
    data["rounds"][0]["axis_deltas"]["industrial_reproduction"] += 1
    with pytest.raises(SimulationError, match="does not match transition rule"):
        run_simulation(data)


def test_fixture_rejects_non_string_evidence_ref():
    data = load_fixture(FIXTURE)
    data["rounds"][0]["evidence_ref"] = 42

    with pytest.raises(SimulationError, match="evidence_ref must be a model-assumption string"):
        run_simulation(data)


def test_fixture_rejects_non_object_top_level(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")

    with pytest.raises(SimulationError, match="fixture must be a JSON object"):
        load_fixture(invalid)


def test_fixture_rejects_null_rounds():
    data = load_fixture(FIXTURE)
    data["rounds"] = None

    with pytest.raises(SimulationError, match="rounds must be a list"):
        run_simulation(data)


@pytest.mark.parametrize("seed", [True, False])
def test_fixture_rejects_boolean_seed(seed):
    data = load_fixture(FIXTURE)
    data["seed"] = seed

    with pytest.raises(SimulationError, match="seed must be an integer"):
        run_simulation(data)


def test_runner_writes_auditable_manifest_and_jsonl_without_overwrite(tmp_path):
    output_dir = tmp_path / "run"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_phase1_fixture.py"), "--output-dir", str(output_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (output_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    trace = [json.loads(line) for line in (output_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]

    assert manifest["schema"] == "space_civilization_stored_run.v1"
    assert manifest["scenario_snapshot_hash"] == result["manifest"]["scenario_snapshot_hash"]
    assert manifest["canonical_output_hash"] == result["canonical_output_hash"]
    assert manifest["event_count"] == len(events)
    assert events == result["events"]
    assert trace == result["trace"]
    assert sha256_json(events) == manifest["event_log_hash"]
    assert len(events) == 4
    assert all(record["causal_scope"] == "model_internal" for record in trace)

    duplicate = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_phase1_fixture.py"), "--output-dir", str(output_dir)],
        capture_output=True,
        text=True,
    )
    assert duplicate.returncode != 0


def test_axis_delta_outside_transition_rule_is_rejected_before_execution():
    data = load_fixture(FIXTURE)
    data["rounds"][0]["axis_deltas"]["industrial_reproduction"] = 1000

    with pytest.raises(SimulationError, match="does not match transition rule"):
        run_simulation(data)
