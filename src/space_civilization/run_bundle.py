"""既存の三分岐runtimeを再検証可能なrun bundleへ薄く投影する。"""

from __future__ import annotations

import json
import math
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .comparison import BRANCHES, compare_simulations
from .simulation import canonical_json, sha256_json, validate_fixture


BUNDLE_SCHEMA = "space-civilization-run-bundle/v1"
ZERO_HASH = "0" * 64
FIXTURE_ALLOWLIST = {
    "international_integration": "fixtures/phase1_international_cooperation.json",
    "domestic_autonomy": "fixtures/phase1_domestic_autonomy.json",
    "open_platform": "fixtures/phase1_open_coordination.json",
}


def reject_duplicate_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """JSON objectの重複キーを全階層で拒否する。"""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_nonfinite_json_constant(value: str) -> Any:
    """JSON仕様外のNaNおよびInfinityを拒否する。"""
    raise ValueError(f"non-finite JSON number: {value}")


def reject_fixture_float_token(value: str) -> Any:
    """fixture契約に存在しないJSON float tokenを変換前に拒否する。"""
    raise ValueError(f"fixture JSON number must be an integer: {value}")


def parse_finite_bundle_float(value: str) -> float:
    """生成側serializerと完全に同じfloat tokenだけを許可する。"""
    try:
        parsed = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"invalid JSON float number: {value}") from error
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    if json.dumps(parsed, allow_nan=False) != value:
        raise ValueError(f"non-canonical JSON float number: {value}")
    return parsed


def parse_canonical_json_int(value: str) -> int:
    """生成側serializerと完全に同じinteger tokenだけを許可する。"""
    parsed = int(value)
    if json.dumps(parsed) != value:
        raise ValueError(f"non-canonical JSON integer: {value}")
    return parsed


def _without_insignificant_json_whitespace(text: str) -> str:
    """文字列内を保持したままJSONの構文上無意味な空白だけを除去する。"""
    compact: list[str] = []
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            compact.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
            compact.append(character)
        elif not character.isspace():
            compact.append(character)
    return "".join(compact)


def load_strict_json(path: str | Path) -> Any:
    """bundle JSONを重複キー・非有限数なしで一度だけ読み込む。"""
    text = Path(path).read_text(encoding="utf-8")
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=reject_duplicate_json_pairs,
            parse_constant=reject_nonfinite_json_constant,
            parse_float=parse_finite_bundle_float,
            parse_int=parse_canonical_json_int,
        )
        canonical = json.dumps(
            parsed,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except RecursionError as error:
        # 拒否経路の例外契約はValueErrorで統一する
        raise ValueError("bundle JSON nesting is too deep") from error
    if _without_insignificant_json_whitespace(text) != canonical:
        raise ValueError("bundle contains non-canonical JSON token spelling or key order")
    return parsed


def load_strict_fixture_json(path: str | Path) -> Any:
    """integer-only fixture JSONを一度だけ読み込む。"""
    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_pairs,
            parse_constant=reject_nonfinite_json_constant,
            parse_float=reject_fixture_float_token,
            parse_int=parse_canonical_json_int,
        )
    except RecursionError as error:
        raise ValueError("fixture JSON nesting is too deep") from error


def _fixture_shared_contract(fixture: dict[str, Any]) -> dict[str, Any]:
    scenario_snapshot_id = fixture.get("scenario_snapshot_id")
    model_version = fixture.get("model_version")
    seed = fixture.get("seed")
    if not isinstance(scenario_snapshot_id, str) or not scenario_snapshot_id.strip():
        raise ValueError("fixture scenario_snapshot_id must be a non-empty string")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("fixture model_version must be a non-empty string")
    if type(seed) is not int:
        raise ValueError("fixture seed must be a strict integer")
    agents = fixture["initial_state"]["agents"]
    if not isinstance(agents, dict):
        raise ValueError("fixture agents must be a JSON object")
    if any(
        not isinstance(agent, dict) or type(agent.get("capacity")) is not int
        for agent in agents.values()
    ):
        raise ValueError("fixture agent capacity must be a strict integer")
    return {
        "scenario_snapshot_id": scenario_snapshot_id,
        "model_version": model_version,
        "seed": seed,
        "initial_state": fixture["initial_state"],
        "rounds": [
            {"year": item["year"], "exogenous_event": item["exogenous_event"]}
            for item in fixture["rounds"]
        ],
    }


def _validated_fixture_paths(
    repo_root: Path, fixture_refs: Mapping[str, str]
) -> dict[str, Path]:
    if set(fixture_refs) != set(BRANCHES):
        raise ValueError("fixture refs must contain the three canonical branches")
    paths: dict[str, Path] = {}
    root = repo_root.resolve()
    for branch in BRANCHES:
        ref = fixture_refs[branch]
        if not isinstance(ref, str) or PurePosixPath(ref).is_absolute() or ".." in PurePosixPath(ref).parts:
            raise ValueError("fixture ref must be a repository-relative path without traversal")
        if ref != FIXTURE_ALLOWLIST[branch]:
            raise ValueError(f"fixture ref is not allowlisted for branch: {branch}")
        path = (root / Path(*PurePosixPath(ref).parts)).resolve()
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ValueError("fixture ref escapes repository root") from error
        if not path.is_file():
            raise ValueError(f"fixture is missing: {ref}")
        paths[branch] = path
    return paths


def build_run_bundle(
    repo_root: str | Path,
    fixture_refs: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    refs = dict(FIXTURE_ALLOWLIST if fixture_refs is None else fixture_refs)
    paths = _validated_fixture_paths(root, refs)
    fixtures: dict[str, dict[str, Any]] = {}
    for branch in BRANCHES:
        fixture = load_strict_fixture_json(paths[branch])
        if not isinstance(fixture, dict):
            raise ValueError("fixture must be a JSON object")
        validate_fixture(fixture, allow_hackathon_demo_branches=True)
        _fixture_shared_contract(fixture)
        fixtures[branch] = fixture
    shared_contract_hashes = {
        sha256_json(_fixture_shared_contract(fixtures[branch])) for branch in BRANCHES
    }
    if len(shared_contract_hashes) != 1:
        raise ValueError("branch fixtures must share one exact canonical input contract")
    comparison = compare_simulations(fixtures)
    scenario_snapshot_hashes = {
        comparison["branches"][branch]["manifest"]["scenario_snapshot_hash"]
        for branch in BRANCHES
    }
    if len(scenario_snapshot_hashes) != 1:
        raise ValueError("branch manifests must share one canonical scenario snapshot hash")
    scenario_snapshot_hash = scenario_snapshot_hashes.pop()
    request_content = {
        "schema": "space-civilization-run-request/v1",
        "seed": comparison["seed"],
        "model_version": comparison["model_version"],
        "fixtures": [
            {
                "branch": branch,
                "ref": refs[branch],
                "sha256": sha256_json(fixtures[branch]),
            }
            for branch in BRANCHES
        ],
    }
    run_id = sha256_json(request_content)
    records: list[dict[str, Any]] = []
    previous_hash = ZERO_HASH
    sequence = 1
    for branch in BRANCHES:
        events = comparison["branches"][branch]["events"]
        for expected_turn, event in enumerate(events, start=1):
            if event.get("turn_id") != expected_turn:
                raise ValueError("core runtime returned a non-contiguous turn_id")
            content = {
                "schema": "space-civilization-run-event/v1",
                "run_id": run_id,
                "sequence": sequence,
                "branch": branch,
                "turn_id": expected_turn,
                "previous_hash": previous_hash,
                "event_hash": sha256_json(event),
                "event": event,
            }
            record_hash = sha256_json(content)
            records.append({**content, "record_hash": record_hash})
            previous_hash = record_hash
            sequence += 1
    replay = {
        "schema": "space-civilization-replay/v1",
        "run_id": run_id,
        "comparison_hash": comparison["comparison_hash"],
        "branches": [
            {
                "branch": branch,
                "event_log_hash": comparison["branches"][branch]["event_log_hash"],
                "canonical_output_hash": comparison["branches"][branch]["canonical_output_hash"],
            }
            for branch in BRANCHES
        ],
    }
    evidence = {
        "schema": "space-civilization-evidence/v1",
        "run_id": run_id,
        "scenario_snapshot_hash": scenario_snapshot_hash,
        "exogenous_event_stream_hash": comparison["exogenous_event_stream_hash"],
        "event_stream_head_hash": previous_hash,
        "event_count": len(records),
        "event_stream_hash": sha256_json(records),
    }
    return {
        "schema": BUNDLE_SCHEMA,
        "run_id": run_id,
        "run_request": {**request_content, "run_id": run_id},
        "event_stream": {
            "schema": "space-civilization-event-stream/v1",
            "run_id": run_id,
            "event_count": len(records),
            "event_stream_hash": sha256_json(records),
            "records": records,
        },
        "replay": replay,
        "evidence": evidence,
    }


def _require_exact_fields(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} has unknown or missing fields")
    return value


def verify_run_bundle(bundle: Any, repo_root: str | Path) -> None:
    top = _require_exact_fields(
        bundle,
        {"schema", "run_id", "run_request", "event_stream", "replay", "evidence"},
        "run bundle",
    )
    if top["schema"] != BUNDLE_SCHEMA:
        raise ValueError("run bundle schema is unsupported")
    request = _require_exact_fields(
        top["run_request"],
        {"schema", "run_id", "seed", "model_version", "fixtures"},
        "run request",
    )
    if type(request["seed"]) is not int:
        raise ValueError("run request seed must be a strict integer")
    fixtures = request["fixtures"]
    if not isinstance(fixtures, list) or len(fixtures) != len(BRANCHES):
        raise ValueError("run request fixtures are invalid")
    refs: dict[str, str] = {}
    for expected_branch, item in zip(BRANCHES, fixtures, strict=True):
        fixture = _require_exact_fields(item, {"branch", "ref", "sha256"}, "fixture")
        if fixture["branch"] != expected_branch or not isinstance(fixture["ref"], str):
            raise ValueError("fixture order or branch is invalid")
        refs[expected_branch] = fixture["ref"]
    expected = build_run_bundle(repo_root, refs)
    try:
        actual = canonical_json(top)
    except RecursionError as error:
        raise ValueError("run bundle nesting is too deep") from error
    if actual != canonical_json(expected):
        raise ValueError("run bundle does not match the canonical runtime replay")


def canonical_bundle_json(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
