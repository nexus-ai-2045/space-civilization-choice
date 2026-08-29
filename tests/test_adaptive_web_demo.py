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
