"""Phase 1: LLMを使わない再現可能な一分岐シミュレーション。"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


AXES = (
    "access_and_operation",
    "industrial_reproduction",
    "rule_shaping",
    "knowledge_continuity",
    "relationship_choice",
    "public_legitimacy",
)
ROUNDS = (2026, 2030, 2035, 2040)
AGENTS = (
    "policy_allocator",
    "domestic_exploration_alliance",
    "transport_and_components_alliance",
    "research_and_next_generation_alliance",
    "international_partners",
)
# Phase 1で許可する行動。SIMULATION_DESIGNの動詞集合をdomestic fixtureへ射影したfail-closed enum。
PHASE1_ALLOWED_ACTIONS = frozenset(
    {
        "allocate_to_domestic_core_components",
        "qualify_redundant_component_supply",
        "expand_maintainer_training",
        "operate_with_domestic_maintenance_chain",
    }
)
CLASSIFICATION = {
    "record_kind": "simulated_transition",
    "epistemic_class": "model_assumption",
    "provenance_type": "deterministic_core",
    "validation_state": "accepted_for_run",
}
EXOGENOUS_EVENT_AXES = {
    "budget_focus_required": "public_legitimacy",
    "single_supplier_disruption": "access_and_operation",
    "experienced_workforce_retirement": "knowledge_continuity",
    "international_interface_revision": "relationship_choice",
}


class SimulationError(ValueError):
    """fixtureまたは状態遷移契約に違反した。"""


def _is_int(value: Any) -> bool:
    """JSON boolはintのsubclassなので、厳密な整数だけを受理する。"""
    return type(value) is int


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_fixture(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_fixture(data)
    return data


def validate_fixture(data: dict[str, Any]) -> None:
    required = {"scenario_snapshot_id", "model_version", "seed", "branch", "initial_state", "rounds"}
    missing = sorted(required - data.keys())
    if missing:
        raise SimulationError(f"fixture required fields missing: {missing}")
    if data["branch"] != "domestic_autonomy":
        raise SimulationError("Phase 1 only has transition rules for domestic_autonomy")
    if not _is_int(data["seed"]):
        raise SimulationError("seed must be an integer")
    if [item.get("year") for item in data["rounds"]] != list(ROUNDS):
        raise SimulationError(f"rounds must be {list(ROUNDS)}")
    state = data["initial_state"]
    if set(state.get("axes", {})) != set(AXES):
        raise SimulationError("initial_state.axes must contain the six canonical axes")
    if set(state.get("agents", {})) != set(AGENTS):
        raise SimulationError("initial_state.agents must contain the five canonical agents")
    for axis, value in state["axes"].items():
        if not _is_int(value) or not 0 <= value <= 100:
            raise SimulationError(f"axis out of range: {axis}")
    for index, item in enumerate(data["rounds"], start=1):
        if not item.get("action") or not item.get("rule_id") or not item.get("evidence_ref"):
            raise SimulationError(f"round {index} lacks trace fields")
        if item.get("action") not in PHASE1_ALLOWED_ACTIONS:
            raise SimulationError(f"round {index} action is not a Phase 1 allowed action")
        if item.get("actor") not in AGENTS:
            raise SimulationError(f"round {index} actor is not a canonical agent")
        if not isinstance(item.get("exogenous_event"), str) or not item["exogenous_event"].strip():
            raise SimulationError(f"round {index} exogenous_event must be non-empty")
        if item["exogenous_event"] not in EXOGENOUS_EVENT_AXES:
            raise SimulationError(f"round {index} exogenous_event has no canonical transition rule")
        deltas = item.get("axis_deltas", {})
        if set(deltas) != set(AXES) or any(not _is_int(v) for v in deltas.values()):
            raise SimulationError(f"round {index} axis_deltas invalid")


def _apply_deltas(axes: dict[str, int], deltas: dict[str, int]) -> dict[str, int]:
    """実適用deltaを加算する。範囲外へ出る入力はfail-closedで拒否する。"""
    after: dict[str, int] = {}
    for axis in AXES:
        value = axes[axis] + deltas[axis]
        if not 0 <= value <= 100:
            raise SimulationError(f"axis out of range after transition: {axis}")
        after[axis] = value
    return after


def _deterministic_draw(seed: int, year: int, exogenous_event: str) -> float:
    """seedとround入力から、環境非依存の[0, 1) drawを生成する。"""
    material = canonical_json({"seed": seed, "year": year, "exogenous_event": exogenous_event})
    numerator = int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:8], "big")
    return numerator / 2**64


def _realize_exogenous_effect(event: str, random_draw: float) -> dict[str, int | str]:
    modifier = -1 if random_draw < 1 / 3 else 0 if random_draw < 2 / 3 else 1
    return {"axis": EXOGENOUS_EVENT_AXES[event], "modifier": modifier}


def build_model_internal_trace(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """event logからTRACE-001用のmodel_internal投影を作る。"""
    records: list[dict[str, Any]] = []
    for event in events:
        records.append(
            {
                "turn_id": event["turn_id"],
                "inputs": deepcopy(event["input"]),
                "action": event["action"],
                "model_rule": event["rule_id"],
                "evidence_refs": [event["evidence_ref"]],
                "causal_scope": "model_internal",
                "base_axis_deltas": deepcopy(event["base_axis_deltas"]),
                "axis_deltas": deepcopy(event["axis_deltas"]),
                "exogenous_effect": deepcopy(event["exogenous_effect"]),
                "random_draw": event["random_draw"],
            }
        )
    return records


def common_scenario_snapshot(fixture: dict[str, Any]) -> dict[str, Any]:
    """BRANCH-001で三分岐が共有するscenario入力だけを抜き出す。

    branch、actor、action、axis_deltas、rule_id、evidence_refは分岐固有の実行入力なので
    共有snapshot hashへ含めない。seed / model_versionはreplay署名の別フィールドとして扱う。
    """
    return {
        "scenario_snapshot_id": fixture["scenario_snapshot_id"],
        "initial_state": deepcopy(fixture["initial_state"]),
        "rounds": [
            {
                "year": item["year"],
                "exogenous_event": item["exogenous_event"],
            }
            for item in fixture["rounds"]
        ],
    }


def run_simulation(fixture: dict[str, Any]) -> dict[str, Any]:
    validate_fixture(fixture)
    # 共有scenario入力だけをhashし、分岐固有の実行入力はevent log側へ分離する。
    scenario_snapshot_hash = sha256_json(common_scenario_snapshot(fixture))
    exogenous_event_stream = [
        {
            "year": item["year"],
            "event": item["exogenous_event"],
            "random_draw": _deterministic_draw(fixture["seed"], item["year"], item["exogenous_event"]),
        }
        for item in fixture["rounds"]
    ]
    manifest = {
        "scenario_snapshot_id": fixture["scenario_snapshot_id"],
        "scenario_snapshot_hash": scenario_snapshot_hash,
        "deterministic_execution_input_hash": sha256_json(fixture),
        "seed": fixture["seed"],
        "model_version": fixture["model_version"],
        "branch_id": fixture["branch"],
        "exogenous_event_stream_hash": sha256_json(exogenous_event_stream),
    }
    state = deepcopy(fixture["initial_state"])
    events: list[dict[str, Any]] = []
    for turn_id, item in enumerate(fixture["rounds"], start=1):
        before = deepcopy(state["axes"])
        exogenous_effect = _realize_exogenous_effect(
            item["exogenous_event"], exogenous_event_stream[turn_id - 1]["random_draw"]
        )
        exogenous_effect["provenance"] = item["exogenous_event"]
        effective_deltas = deepcopy(item["axis_deltas"])
        effective_deltas[exogenous_effect["axis"]] += exogenous_effect["modifier"]
        after = _apply_deltas(before, effective_deltas)
        state["axes"] = after
        events.append(
            {
                "turn_id": turn_id,
                "year": item["year"],
                "actor": item["actor"],
                "input": {"branch": fixture["branch"], "exogenous_event": item["exogenous_event"]},
                "action": item["action"],
                "before": before,
                "after": after,
                "base_axis_deltas": deepcopy(item["axis_deltas"]),
                "axis_deltas": effective_deltas,
                "exogenous_effect": exogenous_effect,
                "rule_id": item["rule_id"],
                "evidence_ref": item["evidence_ref"],
                "random_draw": exogenous_event_stream[turn_id - 1]["random_draw"],
                **CLASSIFICATION,
            }
        )
    event_log_hash = sha256_json(events)
    result = {"manifest": manifest, "final_state": state, "events": events, "event_log_hash": event_log_hash}
    # hash対象はPhase 1のstored run契約（manifest/state/events）に固定する。
    result["canonical_output_hash"] = sha256_json(result)
    result["trace"] = build_model_internal_trace(events)
    return result
