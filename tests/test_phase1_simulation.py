from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_civilization import SimulationError, load_fixture, run_simulation, sha256_json

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


def test_axis_delta_that_requires_clamping_is_rejected():
    data = load_fixture(FIXTURE)
    data["rounds"][0]["axis_deltas"]["industrial_reproduction"] = 1000

    with pytest.raises(SimulationError, match="axis out of range after transition"):
        run_simulation(data)
