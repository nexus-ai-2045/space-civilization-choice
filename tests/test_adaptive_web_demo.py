import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from space_civilization import ai_advisor
from space_civilization.parameter_registry import expand_preset
from space_civilization import web_demo
from space_civilization.web_demo import DemoHandler, build_adaptive_demo


def test_adaptive_demo_exposes_local_engine_and_annual_rounds():
    result = build_adaptive_demo(expand_preset("balanced"), seed=9)

    assert result["decision_engine"] == "deterministic_local_v1"
    assert len(result["simulation"]["rounds"]) == 15
    assert len(result["rounds"]) == 15
    assert result["rounds"][0]["year"] == 2026
    assert result["rounds"][-1]["year"] == 2040
    assert len(result["proposals"]) == 5
    assert len(result["axes"]) == 6
    assert all("domains" in item for item in result["rounds"])
    assert all(len(item["interactions"]) == 5 for item in result["rounds"])
    assert all(
        {"responder_agent_id", "target_agent_id", "stance", "initial_action", "final_action", "final_priority"}
        <= set(interaction)
        for item in result["rounds"]
        for interaction in item["interactions"]
    )


def test_stream_endpoint_emits_honest_annual_progress_and_final_result():
    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/simulate/stream",
            data=json.dumps({"parameters": expand_preset("balanced"), "rounds": 15, "seed": 9}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.headers["Content-Type"].startswith("application/x-ndjson")
            events = [json.loads(line) for line in response]
        assert events[0] == {"event": "year_started", "year": 2026}
        assert events[-1]["event"] == "simulation_completed"
        assert len(events[-1]["result"]["rounds"]) == 15
        assert [item["year"] for item in events if item["event"] == "year_completed"] == list(range(2026, 2041))
    finally:
        server.shutdown()
        server.server_close()


def test_stream_endpoint_rejects_invalid_parameters_before_ndjson_headers():
    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/simulate/stream",
            data=json.dumps({"parameters": {"unknown": 1}, "rounds": 15}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(request, timeout=10)
        assert exc_info.value.code == 400
        assert exc_info.value.headers["Content-Type"] == "application/json"
        assert json.loads(exc_info.value.read()) == {"error": "invalid_simulation_request"}
    finally:
        server.shutdown()
        server.server_close()


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


def test_fallback_batch_route_preserves_four_round_contract(monkeypatch):
    monkeypatch.setattr(web_demo, "adaptive_frontend_available", lambda: False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/simulate",
            data=json.dumps({"rounds": 4}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 200
            assert len(json.load(response)["branches"]) == 3
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


def test_fallback_ui_rejects_supported_shape_inputs_it_cannot_apply(monkeypatch, tmp_path):
    monkeypatch.setattr(web_demo, "FRONTEND_ROOT", tmp_path / "missing-dist")
    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for body in (
            {"parameters": expand_preset("balanced")},
            {"seed": 17},
        ):
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/simulate",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as error:
                assert error.code == 400
            else:
                raise AssertionError("fallback UI must not silently ignore canonical inputs")
    finally:
        server.shutdown()
        server.server_close()


def test_fallback_ui_rejects_explicit_default_seed_that_differs_from_fixture(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(web_demo, "FRONTEND_ROOT", tmp_path / "missing-dist")
    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/simulate",
            data=json.dumps({"seed": 20260829}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("fallback UI must reject every explicit seed")
    finally:
        server.shutdown()
        server.server_close()


def test_fallback_ui_route_is_deterministic_even_with_openai_key(monkeypatch, tmp_path):
    monkeypatch.setattr(web_demo, "FRONTEND_ROOT", tmp_path / "missing-dist")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")

    def fail_if_network_called(*_args, **_kwargs):
        raise AssertionError("fallback server must not call the OpenAI transport")

    monkeypatch.setattr(ai_advisor, "_post_response", fail_if_network_called)
    monkeypatch.setattr(ai_advisor, "propose_action", fail_if_network_called)

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
        assert payload["ai_mode"] == "deterministic_fallback"
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
    for source, view in zip(
        result["simulation"]["rounds"], result["rounds"], strict=True
    ):
        records_by_id = {
            record["execution_record_id"]: record
            for record in source["execution_records"]
        }
        for diagnostic in source["transition_saturations"]:
            assert set(diagnostic) == {"rule_id", "execution_record_id"}
            identity = web_demo._record_identity(
                records_by_id[diagnostic["execution_record_id"]]
            )
            assert any(
                row.startswith("SATURATION ")
                and f'rule={diagnostic["rule_id"]}' in row
                and identity in row
                for row in view["trace"]
            )
    for view in result["rounds"]:
        assert all(
            f'SATURATION year={view["year"]} ' in row
            for row in view["trace"]
            if row.startswith("SATURATION ")
        )


def test_displayed_trace_projects_applied_deltas_for_every_accepted_action():
    result = build_adaptive_demo(expand_preset("balanced"), seed=9)
    for source, view in zip(
        result["simulation"]["rounds"], result["rounds"], strict=True
    ):
        action_rows = [row for row in view["trace"] if row.startswith("ACTION ")]
        for accepted in source["accepted_actions"]:
            for axis in accepted["effects"]:
                assert any(
                    accepted["agent_id"] in row
                    and accepted["action_id"] in row
                    and f"axis={axis}" in row
                    and "applied=" in row
                    for row in action_rows
                )
        assert all(
            row.startswith(("ACTION ", "FEEDBACK ", "SATURATION ", "UNCERTAINTY "))
            for row in view["trace"]
        )


def test_execution_records_include_unsaturated_feedback_and_reconcile_after_state():
    result = build_adaptive_demo(expand_preset("balanced"), seed=9)
    feedback_count = 0
    for source, view in zip(result["simulation"]["rounds"], result["rounds"], strict=True):
        feedback = [
            record for record in view["execution_records"]
            if record["kind"] == "feedback"
        ]
        assert len(feedback) == 1
        feedback_count += 1
        record = feedback[0]
        assert record["rule_id"] == "FEEDBACK-LEGITIMACY"
        assert record["axis"] == "public_legitimacy"
        assert any(
            row.startswith("FEEDBACK ")
            and f'applied={record["applied_delta"]:+d}' in row
            for row in view["trace"]
        )
        assert view["execution_records"] == source["execution_records"]
    assert feedback_count == 15


def test_uncertainty_trace_projects_parameter_identity_for_every_record():
    result = build_adaptive_demo(expand_preset("balanced"), seed=9)
    for view in result["rounds"]:
        records = [
            record for record in view["execution_records"]
            if record["kind"] == "uncertainty"
        ]
        assert len(records) == 3
        for record in records:
            assert any(
                row.startswith("UNCERTAINTY ")
                and f'parameter={record["parameter_id"]}' in row
                and f'rule={record["rule_id"]}' in row
                for row in view["trace"]
            )


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
    assert "AbortController" in source
    assert "reader.cancel()" in source
    assert "setInterval" not in source
    assert "主体間の応答と再提案" in source
    assert "結果リプレイを停止" in source
    responsive = (web_demo.REPO_ROOT / "frontend/src/responsive.css").read_text(encoding="utf-8")
    assert ".timeline {" in responsive
    assert "overflow-x: auto" in responsive
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
