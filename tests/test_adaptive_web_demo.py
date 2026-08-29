import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from space_civilization.parameter_registry import expand_preset
from space_civilization.web_demo import DemoHandler, build_adaptive_demo


def test_adaptive_demo_exposes_local_engine_and_four_rounds():
    result = build_adaptive_demo(expand_preset("balanced"), seed=9)

    assert result["decision_engine"] == "deterministic_local_v1"
    assert len(result["simulation"]["rounds"]) == 4
    assert len(result["proposals"]) == 5
    assert len(result["axes"]) == 6


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
