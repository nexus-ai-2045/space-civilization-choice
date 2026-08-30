"""既存の三分岐runtimeを再検証可能なrun bundleへ薄く投影する。"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .comparison import BRANCHES, compare_simulations
from .simulation import load_fixture, sha256_json


BUNDLE_SCHEMA = "meta-security-run-bundle/v1"
ZERO_HASH = "0" * 64
FIXTURE_ALLOWLIST = {
    "international_integration": "fixtures/phase1_international_cooperation.json",
    "domestic_autonomy": "fixtures/phase1_domestic_autonomy.json",
    "open_platform": "fixtures/phase1_open_coordination.json",
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
    fixtures = {
        branch: load_fixture(
            paths[branch], allow_hackathon_demo_branches=True
        )
        for branch in BRANCHES
    }
    comparison = compare_simulations(fixtures)
    request_content = {
        "schema": "meta-security-run-request/v1",
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
                "schema": "meta-security-run-event/v1",
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
        "schema": "meta-security-replay/v1",
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
        "schema": "meta-security-evidence/v1",
        "run_id": run_id,
        "scenario_snapshot_hash": comparison["branches"][BRANCHES[0]]["manifest"]["scenario_snapshot_hash"],
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
            "schema": "meta-security-event-stream/v1",
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
    if top != expected:
        raise ValueError("run bundle does not match the canonical runtime replay")


def canonical_bundle_json(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
