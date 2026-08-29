from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_civilization.comparison import BRANCHES, compare_simulations


FIXTURES = {
    "international_integration": ROOT / "fixtures/phase1_international_cooperation.json",
    "domestic_autonomy": ROOT / "fixtures/phase1_domestic_autonomy.json",
    "open_platform": ROOT / "fixtures/phase1_open_coordination.json",
}


def test_three_branches_run_four_rounds_under_the_same_exogenous_stream():
    result = compare_simulations(FIXTURES)

    assert result["schema"] == "space_civilization_branch_comparison.v1"
    assert result["branch_order"] == list(BRANCHES)
    assert set(result["branches"]) == set(BRANCHES)
    assert len(result["comparison_hash"]) == 64
    for branch, run in result["branches"].items():
        assert run["manifest"]["branch_id"] == branch
        assert run["manifest"]["exogenous_event_stream_hash"] == result["exogenous_event_stream_hash"]
        assert len(run["events"]) == 4


def test_comparison_is_replayable_and_exposes_all_final_axes():
    first = compare_simulations(FIXTURES)
    second = compare_simulations(FIXTURES)

    assert first == second
    assert set(first["final_axis_comparison"]) == {
        "access_and_operation",
        "industrial_reproduction",
        "rule_shaping",
        "knowledge_continuity",
        "relationship_choice",
        "public_legitimacy",
    }
    assert all(set(values) == set(BRANCHES) for values in first["final_axis_comparison"].values())


def test_comparison_rejects_a_missing_branch():
    incomplete = dict(FIXTURES)
    incomplete.pop("open_platform")

    with pytest.raises(ValueError, match="exactly these branches"):
        compare_simulations(incomplete)


def test_comparison_rejects_non_shared_seed():
    fixtures = {branch: __import__("json").loads(path.read_text(encoding="utf-8")) for branch, path in FIXTURES.items()}
    fixtures["open_platform"]["seed"] += 1

    with pytest.raises(ValueError, match="share seed"):
        compare_simulations(fixtures)
