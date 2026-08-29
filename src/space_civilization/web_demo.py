"""ハッカソン用のゼロ依存ローカルWebデモ。"""

from __future__ import annotations

import json
from copy import deepcopy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .ai_advisor import propose_action
from .comparison import BRANCHES, compare_simulations
from .simulation import apply_action_effect, load_fixture, sha256_json


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPO_ROOT / "web"
FIXTURES = {
    "international_integration": REPO_ROOT / "fixtures/phase1_international_cooperation.json",
    "domestic_autonomy": REPO_ROOT / "fixtures/phase1_domestic_autonomy.json",
    "open_platform": REPO_ROOT / "fixtures/phase1_open_coordination.json",
}


def build_demo_result() -> dict[str, Any]:
    fixtures = {branch: deepcopy(load_fixture(path)) for branch, path in FIXTURES.items()}
    proposals: dict[str, dict[str, str]] = {}
    for branch in BRANCHES:
        context = {
            "branch": branch,
            "year": fixtures[branch]["rounds"][0]["year"],
            "axes": fixtures[branch]["initial_state"]["axes"],
            "exogenous_event": fixtures[branch]["rounds"][0]["exogenous_event"],
        }
        proposal = propose_action(context)
        fixtures[branch]["rounds"][0]["action"] = proposal.action
        fixtures[branch]["rounds"][0]["axis_deltas"] = apply_action_effect(
            proposal.action, fixtures[branch]["rounds"][0]["axis_deltas"]
        )
        proposals[branch] = {
            **proposal.to_dict(),
            "record_kind": "action_proposal",
            "epistemic_class": "inference",
            "provenance_type": "llm" if proposal.source == "openai" else "deterministic_core",
        }

    result = compare_simulations(fixtures)
    result["ai_proposals"] = proposals
    sources = {item["source"] for item in proposals.values()}
    result["ai_mode"] = next(iter(sources)) if len(sources) == 1 else "mixed"
    result["demo_hash"] = sha256_json(result)
    return result


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/simulate":
            self.send_error(404)
            return
        try:
            payload = json.dumps(build_demo_result(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        except Exception:
            payload = json.dumps({"error": "simulation_failed"}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    print(f"Space Civilization Choice: http://{host}:{port}")
    ThreadingHTTPServer((host, port), DemoHandler).serve_forever()
