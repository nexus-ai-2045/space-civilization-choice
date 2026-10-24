from space_civilization import web_demo
from space_civilization.simulation import ACTION_EFFECTS, AXES, SimulationError, apply_action_effect, replace_action_effect, run_simulation
from space_civilization.web_demo import build_demo_result


def test_demo_completes_with_deterministic_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = build_demo_result()

    assert result["ai_mode"] == "deterministic_fallback"
    assert set(result["branches"]) == {
        "international_integration",
        "domestic_autonomy",
        "open_platform",
    }
    assert all(len(run["events"]) == 4 for run in result["branches"].values())
    assert len(result["demo_hash"]) == 64
    assert all(item["validation_state"] == "accepted_for_run" for item in result["ai_proposals"].values())


def test_demo_proposals_are_core_owned_and_replayable(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-affect-demo")
    first = build_demo_result()
    second = build_demo_result()
    assert first["demo_hash"] == second["demo_hash"]
    assert all(
        proposal["source"] == "deterministic_fallback"
        and proposal["provenance_type"] == "deterministic_core"
        for proposal in first["ai_proposals"].values()
    )


def test_adaptive_override_preserves_base_rule_and_uses_distinct_rule(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = build_demo_result()
    for branch, run in result["branches"].items():
        first = run["events"][0]
        assert first["rule_id"] == f"R-ADAPT-{branch}-2026"
        assert first["base_rule_id"].startswith(("R-DOM-", "R-INT-", "R-OPEN-"))
        assert first["base_action"]
        assert run["trace"][0]["base_model_rule"] == first["base_rule_id"]


def test_adaptive_event_preserves_fixture_base_deltas_separately_from_effective_deltas():
    result = build_demo_result()
    for branch, run in result["branches"].items():
        fixture = web_demo.load_fixture(
            web_demo.FIXTURES[branch], allow_hackathon_demo_branches=True
        )
        event = run["events"][0]
        assert event["base_axis_deltas"] == fixture["rounds"][0]["axis_deltas"]
        assert event["axis_deltas"] == {
            axis: event["after"][axis] - event["before"][axis]
            for axis in AXES
        }


def test_domestic_adaptive_override_rejects_forged_base_rule():
    data = web_demo.load_fixture(web_demo.FIXTURES["domestic_autonomy"])
    first = data["rounds"][0]
    first["base_action"] = first["action"]
    first["base_rule_id"] = "R-DOM-FORGED"
    first["base_axis_deltas"] = dict(first["axis_deltas"])
    first["rule_id"] = "R-ADAPT-domestic_autonomy-2026"

    try:
        run_simulation(data)
    except SimulationError as error:
        assert "adaptive base_rule_id invalid" in str(error)
    else:
        raise AssertionError("forged domestic base_rule_id must fail closed")


def test_adaptive_provenance_bundle_rejects_partial_fields():
    data = web_demo.load_fixture(
        web_demo.FIXTURES["international_integration"],
        allow_hackathon_demo_branches=True,
    )
    data["rounds"][0]["base_rule_id"] = data["rounds"][0]["rule_id"]
    try:
        run_simulation(data, allow_hackathon_demo_branches=True)
    except SimulationError as error:
        assert "all present or all absent" in str(error)
    else:
        raise AssertionError("partial adaptive provenance must fail closed")


def test_adaptive_provenance_bundle_rejects_null_wrong_type_and_invalid_values():
    invalid_updates = (
        {"base_rule_id": None},
        {"base_action": None},
        {"base_axis_deltas": None},
        {"base_rule_id": 7},
        {"base_action": "not-allowlisted"},
        {"base_axis_deltas": {axis: False for axis in AXES}},
    )
    for update in invalid_updates:
        data = web_demo.load_fixture(
            web_demo.FIXTURES["international_integration"],
            allow_hackathon_demo_branches=True,
        )
        first = data["rounds"][0]
        first["base_rule_id"] = first["rule_id"]
        first["base_action"] = first["action"]
        first["base_axis_deltas"] = dict(first["axis_deltas"])
        first.update(update)
        try:
            run_simulation(data, allow_hackathon_demo_branches=True)
        except SimulationError as error:
            assert "adaptive provenance" in str(error)
        else:
            raise AssertionError(f"invalid adaptive provenance must fail: {update!r}")


def test_replacing_fixture_action_removes_prior_action_effect():
    base = {axis: 0 for axis in AXES}
    base["industrial_reproduction"] = 8
    base["relationship_choice"] = -3
    previous = "allocate_to_domestic_core_components"
    nxt = "expand_maintainer_training"

    replaced = replace_action_effect(previous, nxt, base)
    expected = dict(base)
    for axis, delta in ACTION_EFFECTS[previous].items():
        expected[axis] -= delta
    for axis, delta in ACTION_EFFECTS[nxt].items():
        expected[axis] += delta
    assert replaced == expected
    # Additive apply would leave the original industrial bump intact.
    additive = apply_action_effect(nxt, base)
    assert additive["industrial_reproduction"] != replaced["industrial_reproduction"]


def test_ui_does_not_render_ai_text_as_html():
    source = (web_demo.REPO_ROOT / "web/app.js").read_text(encoding="utf-8")

    assert "innerHTML" not in source
    assert "textContent" in source


def test_core_rejects_action_without_effect_rule():
    deltas = {axis: 0 for axis in AXES}

    try:
        apply_action_effect("unregistered_action", deltas)
    except SimulationError as error:
        assert "canonical effect rule" in str(error)
    else:
        raise AssertionError("unregistered action must fail closed")
