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
# Phase 1の行動を、その意味を実装する規則とbase deltaへfail-closedで束縛する。
PHASE1_TRANSITION_RULES = {
    "allocate_to_domestic_core_components": {
        "rule_id": "R-DOM-01", "axis_deltas": (-2, 8, 1, 4, -3, 1)
    },
    "qualify_redundant_component_supply": {
        "rule_id": "R-DOM-02", "axis_deltas": (3, 7, 0, 2, 1, 1)
    },
    "expand_maintainer_training": {
        "rule_id": "R-DOM-03", "axis_deltas": (2, 3, 1, 8, 0, 2)
    },
    "operate_with_domestic_maintenance_chain": {
        "rule_id": "R-DOM-04", "axis_deltas": (4, 4, -1, 3, -2, 1)
    },
}
PHASE1_ALLOWED_ACTIONS = frozenset(PHASE1_TRANSITION_RULES)
# ハッカソンdemo用の行動寄与（Phase 1 domestic transition bindingとは別）。
# fixture全体のaxis_deltasから差し替え可能な、コア所有の小さな寄与だけを表す。
ACTION_EFFECTS = {
    "allocate_to_domestic_core_components": {"industrial_reproduction": 3, "relationship_choice": -1},
    "qualify_redundant_component_supply": {"access_and_operation": 3, "industrial_reproduction": 1},
    "expand_maintainer_training": {"knowledge_continuity": 3, "public_legitimacy": 1},
    "operate_with_domestic_maintenance_chain": {"access_and_operation": 2, "rule_shaping": -1},
}
HACKATHON_DEMO_BRANCHES = frozenset({"international_integration", "open_platform"})
HACKATHON_BRANCH_RULES = {
    "international_integration": {
        "R-INT-01": ("qualify_redundant_component_supply", (7, 1, 5, 2, 7, 2)),
        "R-INT-02": ("qualify_redundant_component_supply", (6, 2, 4, 1, 6, 1)),
        "R-INT-03": ("expand_maintainer_training", (3, 1, 5, 5, 5, 2)),
        "R-INT-04": ("operate_with_domestic_maintenance_chain", (6, 0, 6, 2, 6, 1)),
    },
    "open_platform": {
        "R-OPEN-01": ("allocate_to_domestic_core_components", (4, 3, 6, 5, 4, 5)),
        "R-OPEN-02": ("qualify_redundant_component_supply", (5, 4, 5, 3, 4, 3)),
        "R-OPEN-03": ("expand_maintainer_training", (3, 3, 4, 7, 3, 4)),
        "R-OPEN-04": ("operate_with_domestic_maintenance_chain", (4, 3, 5, 4, 4, 4)),
    },
}
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


def deterministic_execution_input_hash(fixture: dict[str, Any]) -> str:
    """実行入力fixtureのcanonical JSON digestを再計算する。"""
    return sha256_json(fixture)


def load_fixture(path: str | Path, *, allow_hackathon_demo_branches: bool = False) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SimulationError("fixture must be a JSON object")
    validate_fixture(data, allow_hackathon_demo_branches=allow_hackathon_demo_branches)
    return data


def validate_fixture(data: dict[str, Any], *, allow_hackathon_demo_branches: bool = False) -> None:
    if not isinstance(data, dict):
        raise SimulationError("fixture must be a JSON object")
    required = {"scenario_snapshot_id", "model_version", "seed", "branch", "initial_state", "rounds"}
    missing = sorted(required - data.keys())
    if missing:
        raise SimulationError(f"fixture required fields missing: {missing}")
    branch = data["branch"]
    if branch == "domestic_autonomy":
        pass
    elif allow_hackathon_demo_branches and branch in HACKATHON_DEMO_BRANCHES:
        pass
    elif branch in HACKATHON_DEMO_BRANCHES:
        raise SimulationError("Phase 1 only has transition rules for domestic_autonomy")
    else:
        raise SimulationError("unknown technology branch")
    if not _is_int(data["seed"]):
        raise SimulationError("seed must be an integer")
    rounds = data["rounds"]
    if not isinstance(rounds, list):
        raise SimulationError("rounds must be a list")
    if [item.get("year") if isinstance(item, dict) else None for item in rounds] != list(ROUNDS):
        raise SimulationError(f"rounds must be {list(ROUNDS)}")
    state = data["initial_state"]
    if not isinstance(state, dict):
        raise SimulationError("initial_state must be an object")
    if set(state.get("axes", {})) != set(AXES):
        raise SimulationError("initial_state.axes must contain the six canonical axes")
    if set(state.get("agents", {})) != set(AGENTS):
        raise SimulationError("initial_state.agents must contain the five canonical agents")
    for axis, value in state["axes"].items():
        if not _is_int(value) or not 0 <= value <= 100:
            raise SimulationError(f"axis out of range: {axis}")
    for index, item in enumerate(rounds, start=1):
        if not isinstance(item, dict):
            raise SimulationError(f"round {index} must be an object")
        evidence_ref = item.get("evidence_ref")
        if (
            not isinstance(evidence_ref, str)
            or not evidence_ref.strip()
            or not evidence_ref.startswith("model-assumption:")
            or not evidence_ref.removeprefix("model-assumption:").strip()
        ):
            raise SimulationError(f"round {index} evidence_ref must be a model-assumption string")
        if not item.get("action") or not item.get("rule_id"):
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
        # 全分岐をそれぞれのcanonical transition ruleへ厳密に束縛する。
        if branch == "domestic_autonomy":
            canonical = PHASE1_TRANSITION_RULES[item.get("base_action", item["action"])]
            expected_rule_id = canonical["rule_id"]
            expected_action = item.get("base_action", item["action"])
            expected_values = canonical["axis_deltas"]
        else:
            expected_rule_id = item.get("base_rule_id", item["rule_id"])
            branch_rule = HACKATHON_BRANCH_RULES[branch].get(expected_rule_id)
            if branch_rule is None:
                raise SimulationError(f"round {index} has no canonical branch transition rule")
            expected_action, expected_values = branch_rule
        base_action = item.get("base_action", item["action"])
        base_deltas = item.get("base_axis_deltas", deltas)
        expected_deltas = dict(zip(AXES, expected_values, strict=True))
        if base_action != expected_action or base_deltas != expected_deltas:
            raise SimulationError(
                f"round {index} does not match transition rule for canonical branch"
            )
        if "base_action" in item:
            expected_adaptive_rule = f"R-ADAPT-{branch}-{item['year']}"
            if item.get("base_rule_id") != expected_rule_id:
                raise SimulationError(f"round {index} adaptive base_rule_id invalid")
            if item.get("rule_id") != expected_adaptive_rule:
                raise SimulationError(f"round {index} adaptive rule_id invalid")
            if deltas != replace_action_effect(base_action, item["action"], base_deltas):
                raise SimulationError(f"round {index} adaptive action effect invalid")
        elif item.get("rule_id") != expected_rule_id or item["action"] != expected_action:
            raise SimulationError(
                f"round {index} does not match transition rule for canonical branch"
            )


def apply_action_effect(action: str, base_deltas: dict[str, int]) -> dict[str, int]:
    """許可済みactionのdemo寄与をコア所有の規則でdeltaへ加算する。"""
    if action not in PHASE1_ALLOWED_ACTIONS or action not in ACTION_EFFECTS:
        raise SimulationError("action has no canonical effect rule")
    if set(base_deltas) != set(AXES) or any(not _is_int(value) for value in base_deltas.values()):
        raise SimulationError("base deltas must contain six integer axes")
    effective = deepcopy(base_deltas)
    for axis, delta in ACTION_EFFECTS[action].items():
        effective[axis] += delta
    return effective


def remove_action_effect(action: str, base_deltas: dict[str, int]) -> dict[str, int]:
    """fixtureに埋め込まれた元action寄与を取り除く。"""
    if action not in PHASE1_ALLOWED_ACTIONS or action not in ACTION_EFFECTS:
        raise SimulationError("action has no canonical effect rule")
    if set(base_deltas) != set(AXES) or any(not _is_int(value) for value in base_deltas.values()):
        raise SimulationError("base deltas must contain six integer axes")
    effective = deepcopy(base_deltas)
    for axis, delta in ACTION_EFFECTS[action].items():
        effective[axis] -= delta
    return effective


def replace_action_effect(previous_action: str, next_action: str, base_deltas: dict[str, int]) -> dict[str, int]:
    """行動置換後のaxis_deltasをコア所有規則から割り当てる。

    domestic fixture（baseが旧actionのtransition ruleと一致）では完全置換する。
    それ以外のdemo fixtureでは、小さなACTION_EFFECTS寄与の差し替えに留める。
    """
    if previous_action not in PHASE1_TRANSITION_RULES or next_action not in PHASE1_TRANSITION_RULES:
        raise SimulationError("action has no canonical effect rule")
    if set(base_deltas) != set(AXES) or any(not _is_int(value) for value in base_deltas.values()):
        raise SimulationError("base deltas must contain six integer axes")
    previous_full = dict(zip(AXES, PHASE1_TRANSITION_RULES[previous_action]["axis_deltas"], strict=True))
    next_full = dict(zip(AXES, PHASE1_TRANSITION_RULES[next_action]["axis_deltas"], strict=True))
    if base_deltas == previous_full:
        return next_full
    without_previous = remove_action_effect(previous_action, base_deltas)
    return apply_action_effect(next_action, without_previous)


def _apply_deltas(axes: dict[str, int], deltas: dict[str, int]) -> dict[str, int]:
    """実適用deltaを加算する。範囲外へ出る入力はfail-closedで拒否する。"""
    after: dict[str, int] = {}
    for axis in AXES:
        value = axes[axis] + deltas[axis]
        if not 0 <= value <= 100:
            raise SimulationError(f"axis out of range after transition: {axis}")
        after[axis] = value
    return after


def deterministic_draw(seed: int, year: int, exogenous_event: str) -> float:
    """seedとround入力から、環境非依存の[0, 1) drawを生成する。"""
    material = canonical_json({"seed": seed, "year": year, "exogenous_event": exogenous_event})
    numerator = int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:8], "big")
    return numerator / 2**64


def realize_exogenous_effect(event: str, random_draw: float) -> dict[str, int | str]:
    modifier = -1 if random_draw < 1 / 3 else 0 if random_draw < 2 / 3 else 1
    return {"axis": EXOGENOUS_EVENT_AXES[event], "modifier": modifier}


def build_model_internal_trace(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """event logからTRACE-001用のmodel_internal投影を作る。"""
    records: list[dict[str, Any]] = []
    for event in events:
        record = {
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
        if event.get("base_rule_id") is not None:
            record["base_model_rule"] = event["base_rule_id"]
            record["base_action"] = event["base_action"]
        records.append(record)
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


def run_simulation(fixture: dict[str, Any], *, allow_hackathon_demo_branches: bool = False) -> dict[str, Any]:
    validate_fixture(fixture, allow_hackathon_demo_branches=allow_hackathon_demo_branches)
    # 共有scenario入力だけをhashし、分岐固有の実行入力はevent log側へ分離する。
    scenario_snapshot_hash = sha256_json(common_scenario_snapshot(fixture))
    exogenous_event_stream = [
        {
            "year": item["year"],
            "event": item["exogenous_event"],
            "random_draw": deterministic_draw(fixture["seed"], item["year"], item["exogenous_event"]),
        }
        for item in fixture["rounds"]
    ]
    manifest = {
        "scenario_snapshot_id": fixture["scenario_snapshot_id"],
        "scenario_snapshot_hash": scenario_snapshot_hash,
        "deterministic_execution_input_hash": deterministic_execution_input_hash(fixture),
        "seed": fixture["seed"],
        "model_version": fixture["model_version"],
        "branch_id": fixture["branch"],
        "exogenous_event_stream_hash": sha256_json(exogenous_event_stream),
    }
    state = deepcopy(fixture["initial_state"])
    events: list[dict[str, Any]] = []
    for turn_id, item in enumerate(fixture["rounds"], start=1):
        before = deepcopy(state["axes"])
        exogenous_effect = realize_exogenous_effect(
            item["exogenous_event"], exogenous_event_stream[turn_id - 1]["random_draw"]
        )
        exogenous_effect["provenance"] = item["exogenous_event"]
        effective_deltas = deepcopy(item["axis_deltas"])
        effective_deltas[exogenous_effect["axis"]] += exogenous_effect["modifier"]
        after = _apply_deltas(before, effective_deltas)
        state["axes"] = after
        event = {
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
        if item.get("base_rule_id") is not None:
            event["base_rule_id"] = item["base_rule_id"]
            event["base_action"] = item["base_action"]
        events.append(event)
    event_log_hash = sha256_json(events)
    result = {"manifest": manifest, "final_state": state, "events": events, "event_log_hash": event_log_hash}
    # hash対象はPhase 1のstored run契約（manifest/state/events）に固定する。
    result["canonical_output_hash"] = sha256_json(result)
    result["trace"] = build_model_internal_trace(events)
    return result
