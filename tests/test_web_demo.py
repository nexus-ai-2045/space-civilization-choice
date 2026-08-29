from space_civilization.ai_advisor import ActionProposal
from space_civilization import web_demo
from space_civilization.simulation import ACTION_EFFECTS, AXES, SimulationError, apply_action_effect, replace_action_effect
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


def test_ai_action_changes_the_simulated_state(monkeypatch):
    def proposal(action):
        return ActionProposal(
            action=action,
            rationale="test",
            source="openai",
            model="test-model",
            prompt_version="test-prompt",
            validation_state="accepted_for_run",
        )

    monkeypatch.setattr(web_demo, "propose_action", lambda _context: proposal("expand_maintainer_training"))
    training = build_demo_result()
    monkeypatch.setattr(web_demo, "propose_action", lambda _context: proposal("qualify_redundant_component_supply"))
    supply = build_demo_result()

    assert training["final_axis_comparison"] != supply["final_axis_comparison"]


def test_adaptive_override_preserves_base_rule_and_uses_distinct_rule(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = build_demo_result()
    for branch, run in result["branches"].items():
        first = run["events"][0]
        assert first["rule_id"] == f"R-ADAPT-{branch}-2026"
        assert first["base_rule_id"].startswith(("R-DOM-", "R-INT-", "R-OPEN-"))
        assert first["base_action"]
        assert run["trace"][0]["base_model_rule"] == first["base_rule_id"]


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
