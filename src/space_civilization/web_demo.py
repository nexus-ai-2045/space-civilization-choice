"""ハッカソン用のゼロ依存ローカルWebデモ。"""

from __future__ import annotations

import json
from copy import deepcopy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .adaptive_loop import run_adaptive_simulation
from .comparison import BRANCHES, compare_simulations
from .parameter_registry import ParameterError, expand_preset
from .simulation import (
    PHASE1_ALLOWED_ACTIONS,
    PHASE1_TRANSITION_RULES,
    load_fixture,
    replace_action_effect,
    sha256_json,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPO_ROOT / "web"
FRONTEND_ROOT = REPO_ROOT / "frontend" / "dist"
FIXTURES = {
    "international_integration": REPO_ROOT / "fixtures/phase1_international_cooperation.json",
    "domestic_autonomy": REPO_ROOT / "fixtures/phase1_domestic_autonomy.json",
    "open_platform": REPO_ROOT / "fixtures/phase1_open_coordination.json",
}


def _deterministic_demo_proposal(context: dict[str, Any]) -> dict[str, str | None]:
    """Return a core-owned proposal without consulting environment or network state."""
    actions = sorted(PHASE1_ALLOWED_ACTIONS)
    action = actions[int(sha256_json(context)[:16], 16) % len(actions)]
    return {
        "action": action,
        "rationale": "入力hashからコア所有の許可済み行動を決定しました。",
        "source": "deterministic_fallback",
        "model": "",
        "prompt_version": "deterministic-demo-v1",
        "validation_state": "accepted_for_run",
        "fallback_reason": None,
    }


def build_demo_result() -> dict[str, Any]:
    fixtures = {
        branch: deepcopy(load_fixture(path, allow_hackathon_demo_branches=True))
        for branch, path in FIXTURES.items()
    }
    proposals: dict[str, dict[str, str]] = {}
    for branch in BRANCHES:
        context = {
            "branch": branch,
            "year": fixtures[branch]["rounds"][0]["year"],
            "axes": fixtures[branch]["initial_state"]["axes"],
            "exogenous_event": fixtures[branch]["rounds"][0]["exogenous_event"],
        }
        proposal = _deterministic_demo_proposal(context)
        previous_action = fixtures[branch]["rounds"][0]["action"]
        fixtures[branch]["rounds"][0]["base_action"] = previous_action
        fixtures[branch]["rounds"][0]["base_rule_id"] = fixtures[branch]["rounds"][0]["rule_id"]
        fixtures[branch]["rounds"][0]["base_axis_deltas"] = deepcopy(
            fixtures[branch]["rounds"][0]["axis_deltas"]
        )
        fixtures[branch]["rounds"][0]["action"] = proposal["action"]
        fixtures[branch]["rounds"][0]["rule_id"] = (
            f"R-ADAPT-{branch}-{fixtures[branch]['rounds'][0]['year']}"
        )
        fixtures[branch]["rounds"][0]["axis_deltas"] = replace_action_effect(
            previous_action, proposal["action"], fixtures[branch]["rounds"][0]["axis_deltas"]
        )
        proposals[branch] = {
            **proposal,
            "record_kind": "action_proposal",
            "epistemic_class": "inference",
            "provenance_type": "deterministic_core",
        }

    result = compare_simulations(fixtures)
    result["ai_proposals"] = proposals
    sources = {item["source"] for item in proposals.values()}
    result["ai_mode"] = next(iter(sources)) if len(sources) == 1 else "mixed"
    result["demo_hash"] = sha256_json(result)
    return result


AXIS_PRESENTATION = {
    "access_and_operation": ("到達・運用", "#ffbf3f"),
    "industrial_reproduction": ("産業再生産", "#24b8ff"),
    "rule_shaping": ("ルール形成", "#9f75ff"),
    "knowledge_continuity": ("知識継承", "#37d3c3"),
    "relationship_choice": ("関係選択", "#ff805d"),
    "public_legitimacy": ("公的正統性", "#c68cff"),
}

ACTION_PRESENTATION = {
    "fund_transport": "宇宙輸送へ重点投資",
    "deploy_autonomy": "自律運用を展開",
    "harden_life_support": "生命維持を強靭化",
    "build_energy_capacity": "宇宙エネルギーを増強",
    "localize_supply": "供給網を国内化",
    "train_people": "宇宙人材を育成",
    "negotiate_standards": "国際標準を共同形成",
    "open_interfaces": "接続仕様を開放",
}

# Map accepted adaptive actions onto the three constellation domains for UI path highlight.
ACTION_DOMAIN = {
    "fund_transport": "physical",
    "deploy_autonomy": "physical",
    "harden_life_support": "physical",
    "build_energy_capacity": "physical",
    "localize_supply": "economic",
    "train_people": "cognitive",
    "negotiate_standards": "economic",
    "open_interfaces": "economic",
}


def _axes_rows(axes: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {"id": axis, "label": AXIS_PRESENTATION[axis][0], "value": value, "color": AXIS_PRESENTATION[axis][1]}
        for axis, value in axes.items()
    ]


def _proposal_rows(round_item: dict[str, Any]) -> list[dict[str, Any]]:
    accepted = {item["agent_id"] for item in round_item["accepted_actions"]}
    return [
        {
            "agent": item["agent_id"],
            "title": ACTION_PRESENTATION[item["action_id"]],
            "action_id": item["action_id"],
            "accepted": item["agent_id"] in accepted,
            "score": 1 if item["agent_id"] in accepted else 0,
            "domain": ACTION_DOMAIN[item["action_id"]],
            "rationale": item["rationale"],
        }
        for item in round_item["proposals"]
    ]


def _trace_rows(
    records: list[dict[str, Any]], saturations: list[dict[str, Any]]
) -> list[str]:
    rows: list[str] = []
    for record in records:
        prefix = record["kind"].upper()
        identity = ""
        if record["kind"] == "action":
            identity = f' agent={record["agent_id"]} action={record["action_id"]}'
        else:
            identity = f' rule={record["rule_id"]}'
        rows.append(
            f'{prefix} year={record["year"]}{identity} axis={record["axis"]} '
            f'attempted={record["attempted_delta"]:+d} '
            f'applied={record["applied_delta"]:+d}'
        )
    rows.extend(
        f'SATURATION rule={event["rule_id"]} axis={event["axis"]} '
        f'attempted={event["attempted_delta"]:+d} '
        f'applied={event["applied_delta"]:+d}'
        for event in saturations
    )
    return rows


def _round_view(round_item: dict[str, Any], round_index: int) -> dict[str, Any]:
    execution_records = round_item["execution_records"]
    return {
        "round": round_index,
        "year": round_item["year"],
        "proposals": _proposal_rows(round_item),
        "axes": _axes_rows(round_item["after"]),
        "trace": _trace_rows(
            execution_records, round_item.get("transition_saturations", [])
        ),
        "execution_records": execution_records,
        "accepted_actions": [item["action_id"] for item in round_item["accepted_actions"]],
        "domains": sorted(
            {
                ACTION_DOMAIN[item["action_id"]]
                for item in round_item["accepted_actions"]
            }
        ),
    }


def build_adaptive_demo(parameters: dict[str, int] | None = None, *, seed: int = 20260829) -> dict[str, Any]:
    result = run_adaptive_simulation(expand_preset("balanced") if parameters is None else parameters, seed=seed)
    round_views = [_round_view(item, index) for index, item in enumerate(result["rounds"], start=1)]
    last = round_views[-1]
    return {
        "schema": "space_civilization_web_demo.v2",
        "round": last["round"],
        "year": last["year"],
        "decision_engine": "deterministic_local_v1",
        "axes": last["axes"],
        "proposals": last["proposals"],
        "trace": [row for item in round_views for row in item["trace"]],
        "rounds": round_views,
        "canonical_output_hash": result["canonical_output_hash"],
        "simulation": result,
    }


def adaptive_frontend_available() -> bool:
    return (FRONTEND_ROOT / "index.html").is_file()


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._adaptive_ui = adaptive_frontend_available()
        static_root = FRONTEND_ROOT if self._adaptive_ui else WEB_ROOT
        super().__init__(*args, directory=str(static_root), **kwargs)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/simulate":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 32_768:
                raise ParameterError("request body size is invalid")
            raw = self.rfile.read(length) if length else b"{}"
            request_body = json.loads(raw.decode("utf-8"))
            if not isinstance(request_body, dict) or set(request_body) - {"parameters", "rounds", "seed"}:
                raise ParameterError("request object contains unknown fields")
            if request_body.get("rounds", 4) != 4:
                raise ParameterError("rounds must be 4")
            seed_supplied = "seed" in request_body
            seed = request_body.get("seed", 20260829)
            if type(seed) is not int:
                raise ParameterError("seed must be a strict integer")
            parameters = request_body.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                raise ParameterError("parameters must be an object")
            # Fallback UI (web/app.js) expects branch_order / branches / ai_mode.
            # Explicit parameter objects are still validated fail-closed even on the
            # legacy route; omission (None) keeps the zero-config fallback demo.
            if self._adaptive_ui:
                body = build_adaptive_demo(parameters, seed=seed)
            else:
                if parameters is not None or seed_supplied:
                    raise ParameterError(
                        "fallback UI cannot represent parameters or an explicit seed"
                    )
                body = build_demo_result()
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        except (ParameterError, UnicodeError, json.JSONDecodeError, ValueError):
            payload = json.dumps({"error": "invalid_simulation_request"}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
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
