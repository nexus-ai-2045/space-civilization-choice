#!/usr/bin/env python3
"""運用採用manifestが保証レベルを過大表示していないか検査する。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "space-civilization-operational-adoption/v1"
CANONICAL_REPOSITORY = "nexus-ai-2045/space-civilization-choice"
LEVELS = {
    "enforced_ci",
    "operator_gate",
    "design_reference",
    "future_candidate",
    "out_of_scope",
}
REQUIRED_IDS = {
    "fractal-decision-ecosystem",
    "engineering-brain",
    "github-ops-skills",
    "worktree-lifecycle-control",
    "repo-preflight",
    "ai-ratchet-gate",
    "internal-workspace-boundary",
    "internal-task-fanin-contract",
    "internal-capability-maturity-model",
    "internal-feedback-ledger-contract",
    "internal-deliberation-runtime",
    "internal-constraint-engine",
    "internal-runtime-process-preflight",
    "voice-interaction-runtime",
    "note-publishing-suite",
}
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")


def _finding(findings: list[dict[str, str]], code: str, **details: str) -> None:
    findings.append({"code": code, **details})


def build_report(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    manifest_path = repo / "ops" / "adoption-manifest.json"
    findings: list[dict[str, str]] = []
    if not manifest_path.is_file():
        _finding(findings, "manifest_missing", path="ops/adoption-manifest.json")
        return _report(findings, [])

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _finding(findings, "manifest_unreadable", detail=str(error))
        return _report(findings, [])

    if manifest.get("schema") != SCHEMA:
        _finding(findings, "schema_mismatch", actual=str(manifest.get("schema", "")))
    if manifest.get("canonical_repository") != CANONICAL_REPOSITORY:
        _finding(
            findings,
            "canonical_repository_mismatch",
            actual=str(manifest.get("canonical_repository", "")),
        )
    if set(manifest.get("levels", {})) != LEVELS:
        _finding(findings, "level_catalog_mismatch")

    entries = manifest.get("entries")
    if not isinstance(entries, list):
        _finding(findings, "entries_not_array")
        return _report(findings, [])

    ids: list[str] = []
    workflow = (repo / ".github" / "workflows" / "ai-ratchet-gate.yml").read_text(
        encoding="utf-8"
    )
    for raw in entries:
        if not isinstance(raw, dict):
            _finding(findings, "entry_not_object")
            continue
        entry_id = raw.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            _finding(findings, "entry_id_missing")
            continue
        ids.append(entry_id)
        level = raw.get("adoption_level")
        visibility = raw.get("source_visibility")
        paths = raw.get("evidence_paths")
        if level not in LEVELS:
            _finding(findings, "invalid_level", entry=entry_id, actual=str(level))
        if visibility not in {"public", "private_internal"}:
            _finding(findings, "invalid_visibility", entry=entry_id)
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            _finding(findings, "invalid_evidence_paths", entry=entry_id)
            paths = []

        repository_url = raw.get("repository_url")
        revision = raw.get("reviewed_revision")
        if visibility == "public":
            if not isinstance(repository_url, str) or not repository_url.startswith(
                "https://github.com/"
            ):
                _finding(findings, "public_repository_url_missing", entry=entry_id)
            if level != "enforced_ci" and not (
                isinstance(revision, str) and HEX40.fullmatch(revision)
            ):
                _finding(findings, "public_revision_invalid", entry=entry_id)
        else:
            if repository_url is not None or revision is not None:
                _finding(findings, "private_source_identity_exposed", entry=entry_id)

        if level in {"future_candidate", "out_of_scope"} and paths:
            _finding(findings, "non_adopted_has_evidence_paths", entry=entry_id)
        if level in {"enforced_ci", "operator_gate", "design_reference"}:
            if not paths:
                _finding(findings, "adopted_without_evidence", entry=entry_id)
            for relative in paths:
                if not (repo / relative).is_file():
                    _finding(
                        findings,
                        "evidence_path_missing",
                        entry=entry_id,
                        path=relative,
                    )

        if level == "enforced_ci":
            release = raw.get("release")
            artifact_hash = raw.get("artifact_sha256")
            if not isinstance(release, str) or not release.startswith("v"):
                _finding(findings, "release_pin_missing", entry=entry_id)
            if not isinstance(artifact_hash, str) or not HEX64.fullmatch(artifact_hash):
                _finding(findings, "artifact_hash_invalid", entry=entry_id)
            elif release not in workflow or artifact_hash not in workflow:
                _finding(findings, "workflow_pin_mismatch", entry=entry_id)

        for field in ("contract", "drift_policy"):
            if not isinstance(raw.get(field), str) or not raw[field].strip():
                _finding(findings, "required_field_missing", entry=entry_id, field=field)

    duplicate_ids = sorted({entry_id for entry_id in ids if ids.count(entry_id) > 1})
    for entry_id in duplicate_ids:
        _finding(findings, "duplicate_entry", entry=entry_id)
    for entry_id in sorted(REQUIRED_IDS - set(ids)):
        _finding(findings, "required_entry_missing", entry=entry_id)
    for entry_id in sorted(set(ids) - REQUIRED_IDS):
        _finding(findings, "unexpected_entry", entry=entry_id)

    return _report(findings, entries)


def _report(findings: list[dict[str, str]], entries: list[Any]) -> dict[str, Any]:
    counts = {level: 0 for level in sorted(LEVELS)}
    for entry in entries:
        if isinstance(entry, dict) and entry.get("adoption_level") in counts:
            counts[entry["adoption_level"]] += 1
    return {
        "schema": "space_civilization_operational_adoption_check.v1",
        "contract_valid": not findings,
        "state": "operational_contract_valid" if not findings else "blocked",
        "counts": counts,
        "findings": findings,
        "external_actions_performed": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="運用採用manifestを検査する。")
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.repo)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"state: {report['state']}")
        for finding in report["findings"]:
            print(f"- {finding}")
    return 0 if report["contract_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
