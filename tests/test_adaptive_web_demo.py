import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from space_civilization.parameter_registry import expand_preset
from space_civilization import web_demo
from space_civilization.web_demo import DemoHandler, build_adaptive_demo


def test_adaptive_demo_exposes_local_engine_and_four_rounds():
    result = build_adaptive_demo(expand_preset("balanced"), seed=9)

    assert result["decision_engine"] == "deterministic_local_v1"
    assert len(result["simulation"]["rounds"]) == 4
    assert len(result["rounds"]) == 4
    assert result["rounds"][0]["year"] == 2026
    assert result["rounds"][-1]["year"] == 2040
    assert len(result["proposals"]) == 5
    assert len(result["axes"]) == 6
    assert all("domains" in item for item in result["rounds"])


def test_http_rejects_unknown_request_fields():
    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/simulate",
            data=json.dumps({"parameters": expand_preset("balanced"), "write_state": True}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("unknown fields must fail closed")
    finally:
        server.shutdown()
        server.server_close()


def test_http_rejects_explicit_empty_parameter_object():
    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/simulate",
            data=json.dumps({"parameters": {}}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("empty parameters must fail closed")
    finally:
        server.shutdown()
        server.server_close()


def test_fallback_ui_route_returns_branch_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(web_demo, "FRONTEND_ROOT", tmp_path / "missing-dist")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/simulate",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert "branch_order" in payload
        assert "branches" in payload
        assert "ai_mode" in payload
        assert "ai_proposals" in payload
    finally:
        server.shutdown()
        server.server_close()


def test_displayed_trace_includes_saturation_records():
    params = expand_preset("balanced")
    params["domestic_supply"] = 100
    params["industrial_capacity"] = 100
    # Keep allocations summing to 100 after boosting domestic_supply.
    params["transport"] = 0
    params["autonomy"] = 0
    params["life_support"] = 0
    params["energy"] = 0
    params["people_research"] = 0
    params["international_connection"] = 0
    params["open_platform"] = 0
    # Rebalance: domestic_supply already 100; others 0 => sum 100.
    params["supply_disruption"] = 0
    result = build_adaptive_demo(params, seed=9)
    saturations = [
        event
        for round_item in result["simulation"]["rounds"]
        for event in round_item["transition_saturations"]
    ]
    assert saturations, "fixture must produce at least one BOUND-* saturation"
    joined = "\n".join(row for view in result["rounds"] for row in view["trace"])
    assert any(event["rule_id"] in joined for event in saturations)
    assert "attempted=" in joined and "applied=" in joined


def test_constellation_scene_destroys_children_on_redraw():
    source = (web_demo.REPO_ROOT / "frontend/src/ConstellationScene.ts").read_text(encoding="utf-8")
    assert "killAll()" in source
    assert "destroy(true)" in source
    assert "removeAll(true)" not in source or "clearDisplayObjects" in source


def test_adaptive_ui_exposes_replay_hash_and_full_pdca_round_labels():
    source = (web_demo.REPO_ROOT / "frontend/src/main.ts").read_text(encoding="utf-8")
    assert "canonical_output_hash" in source
    assert "再実行hash" in source
    assert "replay-hash" in source
    assert "Plan→Do→Check→Act" in source
    assert "年ごと完全PDCA" in source
    assert "['計画 (Plan)','実行 (Do)','評価 (Check)','改善 (Act)']" not in source


def test_adaptive_view_projects_and_renders_proposal_rationale():
    result = build_adaptive_demo(expand_preset("balanced"), seed=10)
    assert all(
        proposal["rationale"]
        for view in result["rounds"]
        for proposal in view["proposals"]
    )
    source = (web_demo.REPO_ROOT / "frontend/src/main.ts").read_text(encoding="utf-8")
    types = (web_demo.REPO_ROOT / "frontend/src/types.ts").read_text(encoding="utf-8")
    assert "proposal-rationale" in source
    assert "p.rationale" in source
    assert "rationale:string" in types


def test_adaptive_ui_ignores_superseded_simulation_responses():
    source = (web_demo.REPO_ROOT / "frontend/src/main.ts").read_text(encoding="utf-8")
    assert "let runGeneration=0" in source
    assert "const generation=++runGeneration" in source
    assert source.count("if(generation!==runGeneration)return") >= 2
