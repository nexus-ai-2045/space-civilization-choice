"""同一条件から三つの技術選択を比較する決定論的シミュレーション。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .simulation import AXES, load_fixture, run_simulation, sha256_json


BRANCHES = ("international_integration", "domestic_autonomy", "open_platform")


def compare_simulations(fixtures: Mapping[str, dict[str, Any] | str | Path]) -> dict[str, Any]:
    """同一snapshot/seed/外生事象から三分岐を実行し、比較可能なJSON値を返す。"""
    if set(fixtures) != set(BRANCHES):
        raise ValueError(f"fixtures must contain exactly these branches: {list(BRANCHES)}")

    loaded = {
        branch: load_fixture(value) if isinstance(value, (str, Path)) else value
        for branch, value in fixtures.items()
    }
    for branch, fixture in loaded.items():
        if fixture.get("branch") != branch:
            raise ValueError(f"fixture branch mismatch: expected {branch}")

    reference = loaded[BRANCHES[0]]
    shared_fields = ("scenario_snapshot_id", "model_version", "seed", "initial_state")
    for branch in BRANCHES[1:]:
        for field in shared_fields:
            if loaded[branch].get(field) != reference.get(field):
                raise ValueError(f"branch fixtures must share {field}")
        reference_events = [item.get("exogenous_event") for item in reference["rounds"]]
        branch_events = [item.get("exogenous_event") for item in loaded[branch]["rounds"]]
        if branch_events != reference_events:
            raise ValueError("branch fixtures must share the exogenous event stream")

    runs = {branch: run_simulation(loaded[branch]) for branch in BRANCHES}
    stream_hashes = {run["manifest"]["exogenous_event_stream_hash"] for run in runs.values()}
    if len(stream_hashes) != 1:
        raise ValueError("branch runs did not realize the same exogenous event stream")

    result: dict[str, Any] = {
        "schema": "space_civilization_branch_comparison.v1",
        "scenario_snapshot_id": reference["scenario_snapshot_id"],
        "model_version": reference["model_version"],
        "seed": reference["seed"],
        "exogenous_event_stream_hash": stream_hashes.pop(),
        "branch_order": list(BRANCHES),
        "branches": runs,
        "final_axis_comparison": {
            axis: {branch: runs[branch]["final_state"]["axes"][axis] for branch in BRANCHES}
            for axis in AXES
        },
    }
    result["comparison_hash"] = sha256_json(result)
    return result
