#!/usr/bin/env python3
"""Project goal contract の構造、文書間整合、状態遷移を検査する。"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


REQUIRED_FILES = (
    "LICENSE",
    "PROJECT_GOAL.md",
    "PROJECT_SSOT.md",
    "PUBLIC_READY.md",
    "README.md",
    "SECURITY.md",
    "docs/ONE_PAGER.md",
    "docs/PRODUCT_SPEC.md",
    "docs/REUSE_MAP.md",
    "docs/ROADMAP.md",
    "docs/SIMULATION_DESIGN.md",
    "docs/RESEARCH_EVIDENCE.md",
    "docs/adr/0005-adaptive-exploratory-decision-loop.md",
    "docs/adr/0006-separate-epistemic-provenance-validation.md",
    "docs/adr/README.md",
)

GOAL_ID = "space-civilization-choice-mvp-v1"
OWNER = "repository-maintainers"
GOAL_STATUSES = {"design", "active", "complete"}
CANONICAL_REPOSITORY = "nexus-ai-2045/space-civilization-choice"
CANONICAL_REPOSITORY_URL = f"https://github.com/{CANONICAL_REPOSITORY}"
REQUIRED_CI_JOBS = (
    "goal-contract",
    "secret-scan",
    "ratchet (ubuntu-latest)",
    "ratchet (windows-latest)",
)
LiveVerifier = Callable[[str, dict[str, Any]], dict[str, Any]]
HeadResolver = Callable[[Path], str]
PersonalPathScanner = Callable[[Path], tuple[bool, list[str]]]

REQUIRED_GOAL_HEADINGS = (
    "ゴール",
    "メタ安全保障との関係",
    "スコープ",
    "非目標",
    "実行契約",
    "完了条件",
    "現在の達成状態",
    "最小PDCAとフィードバックループ",
    "外部境界",
    "戻り先",
)

DONE_WHEN_IDS = (
    "GOAL-001",
    "REPLAY-001",
    "BRANCH-001",
    "TRACE-001",
    "CLASS-001",
    "MODEL-001",
    "ROBUST-001",
    "FEEDBACK-001",
    "HUMAN-001",
    "CI-001",
    "PUBLIC-001",
)

DONE_WHEN_EVIDENCE_SCHEMA = "space_civilization_done_when_evidence.v1"
DONE_WHEN_EVIDENCE_CONTRACTS: dict[str, dict[str, Any]] = {
    "GOAL-001": {
        "evidence_type": "contract_consistency",
        "artifacts": {
            "goal_contract": r"^PROJECT_GOAL\.md$",
            "readme": r"^README\.md$",
            "product_spec": r"^docs/PRODUCT_SPEC\.md$",
        },
    },
    "REPLAY-001": {
        "evidence_type": "deterministic_replay",
        "artifacts": {
            "test": r"^tests/.+\.py$",
            "run_manifest": r"^(?:evidence|artifacts)/runs/.+\.json$",
        },
    },
    "BRANCH-001": {
        "evidence_type": "common_branch_inputs",
        "artifacts": {
            "test": r"^tests/.+\.py$",
            "run_manifest": r"^(?:evidence|artifacts)/runs/.+\.json$",
        },
    },
    "TRACE-001": {
        "evidence_type": "transition_trace",
        "artifacts": {
            "test": r"^tests/.+\.py$",
            "trace": r"^(?:evidence|artifacts)/runs/.+\.jsonl?$",
        },
    },
    "CLASS-001": {
        "evidence_type": "epistemic_schema_validation",
        "artifacts": {
            "test": r"^tests/.+\.py$",
            "validation_report": r"^(?:evidence|artifacts)/reports/.+\.json$",
        },
    },
    "MODEL-001": {
        "evidence_type": "model_parameter_validation",
        "artifacts": {
            "test": r"^tests/.+\.py$",
            "model_card": r"^docs/model-cards/.+\.md$",
        },
    },
    "ROBUST-001": {
        "evidence_type": "robustness_holdout",
        "artifacts": {
            "test": r"^tests/.+\.py$",
            "robustness_report": r"^(?:evidence|artifacts)/reports/.+\.json$",
        },
    },
    "FEEDBACK-001": {
        "evidence_type": "feedback_record",
        "artifacts": {
            "feedback_record": r"^(?:evidence|artifacts)/feedback/.+\.json$",
        },
    },
    "HUMAN-001": {
        "evidence_type": "human_review",
        "artifacts": {
            "review_record": r"^(?:evidence|artifacts)/reviews/.+\.json$",
        },
    },
    "CI-001": {
        "evidence_type": "exact_head_ci",
        "artifacts": {
            "workflow": r"^\.github/workflows/.+\.ya?ml$",
            "ci_receipt": r"^(?:evidence|artifacts)/ci/.+\.json$",
        },
    },
    "PUBLIC-001": {
        "evidence_type": "public_readback",
        "artifacts": {
            "checklist": r"^PUBLIC_READY\.md$",
            "readback": r"^(?:evidence|artifacts)/publication/.+\.json$",
        },
    },
}

REQUIRED_LINKS = {
    "README.md": ("PROJECT_GOAL.md", "PROJECT_SSOT.md"),
    "PROJECT_SSOT.md": (
        "PROJECT_GOAL.md",
        "docs/ONE_PAGER.md",
        "docs/SIMULATION_DESIGN.md",
        "docs/RESEARCH_EVIDENCE.md",
        "docs/adr/README.md",
        "docs/REUSE_MAP.md",
        "PUBLIC_READY.md",
    ),
    "docs/ROADMAP.md": ("../PROJECT_GOAL.md",),
    "docs/adr/README.md": (
        "0005-adaptive-exploratory-decision-loop.md",
        "0006-separate-epistemic-provenance-validation.md",
    ),
}

ADR_CONTRACTS = {
    "docs/adr/0005-adaptive-exploratory-decision-loop.md": (
        "XLRM",
        "ensemble manifest",
        "MPC",
    ),
    "docs/adr/0006-separate-epistemic-provenance-validation.md": (
        "epistemic-provenance-validation/v1",
    ),
}

ADR_SCHEMA_ROWS = {
    "record_kind": (
        "source_claim",
        "exogenous_event",
        "simulated_transition",
        "action_proposal",
    ),
    "epistemic_class": (
        "fact",
        "scenario_hypothesis",
        "model_assumption",
        "inference",
        "unknown",
    ),
    "provenance_type": (
        "official_source",
        "academic_source",
        "third_party_public_source",
        "human_input",
        "deterministic_core",
        "llm",
    ),
    "validation_state": (
        "proposed",
        "accepted_for_run",
        "rejected",
        "superseded",
    ),
}

SSOT_CANONICAL_ROWS = {
    "product_goal": "PROJECT_GOAL.md",
    "scenario": "docs/ONE_PAGER.md",
    "simulation_contract": "docs/SIMULATION_DESIGN.md",
    "research_evidence": "docs/RESEARCH_EVIDENCE.md",
    "decisions": "docs/adr/README.md",
    "reuse_boundary": "docs/REUSE_MAP.md",
    "public_readiness": "PUBLIC_READY.md",
}

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
CHECKBOX_RE = re.compile(
    r"^- \[(?P<checked>[ xX])\] `(?P<id>[A-Z]+-\d{3})`: (?P<body>.+)$",
    re.MULTILINE,
)
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\((?P<target>[^)]+)\)")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<info>[^\r\n]*)$")


def _read(repo: Path, relative: str) -> str:
    return (repo / relative).read_text(encoding="utf-8")


def _strip_fenced_blocks(text: str) -> tuple[str, bool, bool]:
    """fence本文を除去し、未終端fence/commentの有無を返す。"""
    output: list[str] = []
    marker_char = ""
    marker_length = 0
    in_comment = False

    def advance_comment_state(line: str, current: bool) -> bool:
        position = 0
        while position < len(line):
            token = "-->" if current else "<!--"
            found = line.find(token, position)
            if found < 0:
                return current
            current = not current
            position = found + len(token)
        return current

    for line in text.splitlines(keepends=True):
        logical_line = line.rstrip("\r\n")
        if not marker_char:
            if in_comment:
                in_comment = advance_comment_state(logical_line, in_comment)
                output.append(line)
                continue
            match = FENCE_OPEN_RE.fullmatch(logical_line)
            if match and not (
                match.group("marker").startswith("`")
                and "`" in match.group("info")
            ):
                marker_char = match.group("marker")[0]
                marker_length = len(match.group("marker"))
                output.append("\n" if line.endswith(("\n", "\r")) else "")
                continue
            in_comment = advance_comment_state(logical_line, in_comment)
            output.append(line)
            continue

        closing = re.fullmatch(
            rf" {{0,3}}{re.escape(marker_char)}{{{marker_length},}}\s*",
            logical_line,
        )
        if closing:
            marker_char = ""
            marker_length = 0
        output.append("\n" if line.endswith(("\n", "\r")) else "")
    return "".join(output), bool(marker_char), in_comment


def _content(text: str) -> str:
    """front matter、code fence、HTML commentを構造検査の対象外にする。"""
    text = FRONT_MATTER_RE.sub("", text, count=1)
    text = _strip_fenced_blocks(text)[0]
    return COMMENT_RE.sub("", text)


def _front_matter(text: str) -> dict[str, str]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}
    values: dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        if not raw_line or raw_line[0].isspace() or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _markdown_links(text: str) -> set[str]:
    return {
        match.group("target").split("#", 1)[0]
        for match in LINK_RE.finditer(_content(text))
    }


def _resolved_link(repo: Path, source: str, target: str) -> Path | None:
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return None
    candidate = ((repo / source).parent / target).resolve()
    try:
        candidate.relative_to(repo)
    except ValueError:
        return None
    return candidate


def _finding(findings: list[dict[str, str]], code: str, **values: str) -> None:
    findings.append({"code": code, **values})


def _evidence_error(
    findings: list[dict[str, str]],
    goal_id: str,
    reason: str,
    **values: str,
) -> None:
    _finding(
        findings,
        "invalid_done_when_evidence",
        value=goal_id,
        reason=reason,
        **values,
    )


def _is_digest(value: Any, length: int = 64) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(rf"[0-9a-f]{{{length}}}", value)
    )


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _resolve_git_head(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    head_sha = completed.stdout.strip().lower()
    if not _is_digest(head_sha, length=40):
        raise ValueError("git HEAD is not a full SHA")
    return head_sha


def _scan_tracked_personal_paths(repo: Path) -> tuple[bool, list[str]]:
    """cleanなHEADのtracked textだけを上限付きで直接走査する。"""
    clean = subprocess.run(
        ["git", "-C", str(repo), "diff", "--quiet", "--no-ext-diff", "HEAD", "--"],
        check=False,
        timeout=15,
    )
    if clean.returncode != 0:
        raise ValueError("tracked worktree differs from inspected HEAD")
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
        timeout=15,
    ).stdout
    if len(listed) > 2_000_000:
        raise ValueError("tracked path inventory exceeds byte budget")
    raw_paths = [item for item in listed.split(b"\0") if item]
    if len(raw_paths) > 5_000:
        raise ValueError("tracked path inventory exceeds file budget")

    pattern = re.compile(
        r"(?i)(?:[a-z]:[\\/]+Users[\\/]+[^\\/\s]+|(?<![:\w])/(?:Users|home)/[^/\s]+)"
    )
    findings: list[str] = []
    total_bytes = 0
    for raw_path in raw_paths:
        relative = raw_path.decode("utf-8", errors="strict")
        candidate = (repo / relative).resolve()
        try:
            candidate.relative_to(repo)
        except ValueError as error:
            raise ValueError("tracked path escapes repository") from error
        data = candidate.read_bytes()
        total_bytes += len(data)
        if len(data) > 2_000_000 or total_bytes > 20_000_000:
            raise ValueError("tracked text scan exceeds content budget")
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if pattern.search(text):
            findings.append(relative.replace("\\", "/"))
    return not findings, sorted(findings)


def _github_json(api_path: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com{api_path}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "space-civilization-choice-goal-gate",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("GitHub API response is not an object")
    return payload


def _default_live_verifier(
    goal_id: str, evidence: dict[str, Any]
) -> dict[str, Any]:
    """CI/PUBLICの自己申告をGitHub公開APIでread-backする。"""
    if goal_id == "CI-001":
        run_url = evidence.get("run_url")
        match = re.fullmatch(
            rf"{re.escape(CANONICAL_REPOSITORY_URL)}/actions/runs/(?P<run_id>[1-9]\d*)",
            run_url if isinstance(run_url, str) else "",
        )
        if not match:
            raise ValueError("run URL is not canonical")
        run_id = match.group("run_id")
        run = _github_json(
            f"/repos/{CANONICAL_REPOSITORY}/actions/runs/{run_id}"
        )
        jobs_payload = _github_json(
            f"/repos/{CANONICAL_REPOSITORY}/actions/runs/{run_id}/jobs?per_page=100"
        )
        repository = run.get("repository")
        jobs = jobs_payload.get("jobs")
        return {
            "repository": repository.get("full_name")
            if isinstance(repository, dict)
            else None,
            "head_sha": run.get("head_sha"),
            "conclusion": run.get("conclusion"),
            "run_url": run.get("html_url"),
            "jobs": {
                job.get("name"): job.get("conclusion")
                for job in jobs
                if isinstance(job, dict) and isinstance(job.get("name"), str)
            }
            if isinstance(jobs, list)
            else None,
        }
    if goal_id == "PUBLIC-001":
        repository = _github_json(f"/repos/{CANONICAL_REPOSITORY}")
        main = _github_json(f"/repos/{CANONICAL_REPOSITORY}/commits/main")
        head_sha = evidence.get("head_sha")
        files: dict[str, bool] = {}
        for path in ("README.md", "LICENSE", "SECURITY.md"):
            encoded_path = urllib.parse.quote(path, safe="")
            encoded_ref = urllib.parse.quote(
                head_sha if isinstance(head_sha, str) else "", safe=""
            )
            contents = _github_json(
                f"/repos/{CANONICAL_REPOSITORY}/contents/{encoded_path}?ref={encoded_ref}"
            )
            files[path] = (
                contents.get("type") == "file" and contents.get("path") == path
            )
        return {
            "repository": repository.get("full_name"),
            "visibility": repository.get("visibility"),
            "default_branch": repository.get("default_branch"),
            "main_head": main.get("sha"),
            "repository_url": repository.get("html_url"),
            "files": files,
        }
    raise ValueError(f"unsupported live verification goal: {goal_id}")


def _read_json_evidence(
    path: Path,
    goal_id: str,
    role: str,
    findings: list[dict[str, str]],
) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _evidence_error(
            findings,
            goal_id,
            "artifact_invalid_json",
            artifact_role=role,
            target=path.as_posix(),
        )
        return None


def _validate_test_evidence(
    path: Path,
    goal_id: str,
    required_tokens: tuple[str, ...],
    findings: list[dict[str, str]],
) -> None:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeError, SyntaxError):
        _evidence_error(
            findings,
            goal_id,
            "test_artifact_invalid_python",
            target=path.as_posix(),
        )
        return
    has_test = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test")
        for node in ast.walk(tree)
    )
    has_assertion = any(
        isinstance(node, ast.Assert)
        or (
            isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
            and (
                getattr(node.func, "id", "").startswith("assert")
                or getattr(node.func, "attr", "").startswith("assert")
            )
        )
        for node in ast.walk(tree)
    )
    missing_tokens = [token for token in required_tokens if token not in source]
    if not has_test or not has_assertion or missing_tokens:
        _evidence_error(
            findings,
            goal_id,
            "test_artifact_missing_contract",
            target=path.as_posix(),
            missing="|".join(missing_tokens),
        )


def _validate_done_when_artifact_contents(
    goal_id: str,
    paths: dict[str, Path],
    receipt: dict[str, Any],
    findings: list[dict[str, str]],
    repo: Path,
    live_verifier: LiveVerifier,
    head_resolver: HeadResolver,
    personal_path_scanner: PersonalPathScanner,
) -> None:
    """11個のdone_whenごとに、自己申告ではない最小証拠構造を検証する。"""
    if goal_id == "GOAL-001":
        result = receipt.get("result")
        expected_documents = ["PROJECT_GOAL.md", "README.md", "docs/PRODUCT_SPEC.md"]
        if not isinstance(result, dict) or not (
            result.get("consistent") is True
            and result.get("documents") == expected_documents
        ):
            _evidence_error(findings, goal_id, "goal_consistency_result_invalid")
        return

    if goal_id == "REPLAY-001":
        _validate_test_evidence(
            paths["test"],
            goal_id,
            ("replay", "scenario_snapshot_hash", "canonical_output_hash"),
            findings,
        )
        manifest = _read_json_evidence(paths["run_manifest"], goal_id, "run_manifest", findings)
        if not isinstance(manifest, dict):
            return
        replays = manifest.get("replays")
        valid = manifest.get("schema") == "space_civilization_run_manifest.v1"
        valid = valid and isinstance(replays, list) and len(replays) >= 2
        if valid:
            signatures: set[tuple[Any, Any, Any]] = set()
            outputs: set[str] = set()
            for run in replays:
                if not isinstance(run, dict):
                    valid = False
                    break
                signatures.add(
                    (
                        run.get("scenario_snapshot_hash"),
                        run.get("seed"),
                        run.get("model_version"),
                    )
                )
                output_hash = run.get("canonical_output_hash")
                if not _is_digest(output_hash):
                    valid = False
                else:
                    outputs.add(output_hash)
            valid = valid and len(signatures) == 1 and len(outputs) == 1
        if not valid:
            _evidence_error(findings, goal_id, "replay_result_invalid")
        return

    if goal_id == "BRANCH-001":
        _validate_test_evidence(
            paths["test"],
            goal_id,
            ("branch", "scenario_snapshot_hash", "exogenous_event_stream_hash"),
            findings,
        )
        manifest = _read_json_evidence(paths["run_manifest"], goal_id, "run_manifest", findings)
        if not isinstance(manifest, dict):
            return
        branches = manifest.get("branches")
        valid = manifest.get("schema") == "space_civilization_run_manifest.v1"
        valid = valid and isinstance(branches, list) and len(branches) == 3
        if valid:
            branch_ids: set[str] = set()
            common_inputs: set[tuple[Any, Any, Any, Any]] = set()
            event_log_hashes: set[str] = set()
            for branch in branches:
                if not isinstance(branch, dict) or not isinstance(
                    branch.get("branch_id"), str
                ):
                    valid = False
                    break
                branch_ids.add(branch["branch_id"])
                common_inputs.add(
                    (
                        branch.get("scenario_snapshot_hash"),
                        branch.get("seed"),
                        branch.get("model_version"),
                        branch.get("exogenous_event_stream_hash"),
                    )
                )
                event_log_hash = branch.get("event_log_hash")
                if not _is_digest(event_log_hash):
                    valid = False
                else:
                    event_log_hashes.add(event_log_hash)
            valid = valid and len(branch_ids) == 3 and len(common_inputs) == 1
            valid = valid and len(event_log_hashes) == 3
            if valid:
                common = next(iter(common_inputs))
                valid = _is_digest(common[0]) and _is_digest(common[3])
                valid = valid and bool(common[2])
        if not valid:
            _evidence_error(findings, goal_id, "branch_result_invalid")
        return

    if goal_id == "TRACE-001":
        _validate_test_evidence(
            paths["test"],
            goal_id,
            ("turn_id", "evidence_ref", "model_internal"),
            findings,
        )
        trace_path = paths["trace"]
        if trace_path.suffix == ".jsonl":
            try:
                records = [
                    json.loads(line)
                    for line in trace_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except (OSError, UnicodeError, json.JSONDecodeError):
                records = None
        else:
            payload = _read_json_evidence(trace_path, goal_id, "trace", findings)
            records = payload.get("records") if isinstance(payload, dict) else payload
        valid = isinstance(records, list) and bool(records)
        required = ("turn_id", "inputs", "action", "model_rule", "evidence_refs")
        if valid:
            for record in records:
                valid = isinstance(record, dict) and all(
                    record.get(field) not in (None, "", [], {}) for field in required
                )
                valid = valid and record.get("causal_scope") == "model_internal"
                valid = valid and isinstance(record.get("axis_deltas"), dict)
                valid = valid and len(record["axis_deltas"]) == 6
                if not valid:
                    break
        if not valid:
            _evidence_error(findings, goal_id, "trace_result_invalid")
        return

    if goal_id == "CLASS-001":
        _validate_test_evidence(
            paths["test"],
            goal_id,
            ("record_kind", "epistemic_class", "provenance_type", "validation_state"),
            findings,
        )
        report = _read_json_evidence(
            paths["validation_report"], goal_id, "validation_report", findings
        )
        expected_fields = list(ADR_SCHEMA_ROWS)
        valid = isinstance(report, dict) and (
            report.get("schema") == "epistemic-provenance-validation-report/v1"
            and _positive_int(report.get("records_checked"))
            and report.get("invalid_combinations") == 0
            and report.get("required_fields") == expected_fields
            and report.get("schema_validation_passed") is True
        )
        if not valid:
            _evidence_error(findings, goal_id, "classification_result_invalid")
        return

    if goal_id == "MODEL-001":
        _validate_test_evidence(
            paths["test"],
            goal_id,
            ("unit", "range", "sensitivity", "falsification"),
            findings,
        )
        try:
            model_card = paths["model_card"].read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            model_card = ""
        required_markers = (
            "schema: space_civilization_model_card.v1",
            "unit:",
            "range:",
            "basis:",
            "update_equation:",
            "sensitivity:",
            "falsification_condition:",
        )
        result = receipt.get("result")
        valid = all(marker in model_card for marker in required_markers)
        valid = valid and isinstance(result, dict)
        if valid:
            valid = _positive_int(result.get("parameter_count"))
            valid = valid and result.get("validated_parameter_count") == result.get(
                "parameter_count"
            )
        if not valid:
            _evidence_error(findings, goal_id, "model_parameter_result_invalid")
        return

    if goal_id == "ROBUST-001":
        _validate_test_evidence(
            paths["test"],
            goal_id,
            ("xlrm", "holdout", "regret", "robustness"),
            findings,
        )
        report = _read_json_evidence(
            paths["robustness_report"], goal_id, "robustness_report", findings
        )
        valid = isinstance(report, dict) and report.get("schema") == (
            "space_civilization_robustness_report.v1"
        )
        if valid:
            xlrm = report.get("xlrm")
            valid = isinstance(xlrm, dict) and all(
                isinstance(xlrm.get(field), list) and bool(xlrm[field])
                for field in ("uncertainties", "levers", "relationships", "measures")
            )
            valid = valid and bool(report.get("performance_thresholds"))
            valid = valid and _is_digest(report.get("ensemble_manifest_hash"))
            valid = valid and bool(report.get("robustness_definition"))
            valid = valid and bool(report.get("regret_definition"))
            valid = valid and bool(report.get("holdout_cases"))
            valid = valid and report.get("holdout_passed") is True
            valid = valid and bool(report.get("vulnerabilities"))
            valid = valid and bool(report.get("option_loss_conditions"))
        if not valid:
            _evidence_error(findings, goal_id, "robustness_result_invalid")
        return

    if goal_id == "FEEDBACK-001":
        report = _read_json_evidence(
            paths["feedback_record"], goal_id, "feedback_record", findings
        )
        runs = report.get("runs") if isinstance(report, dict) else None
        valid = isinstance(report, dict) and (
            report.get("schema") == "space_civilization_feedback.v1"
            and isinstance(runs, list)
            and bool(runs)
        )
        if valid:
            required = ("owner", "decision", "next_action", "resume_condition", "evidence")
            valid = all(
                isinstance(run, dict)
                and all(run.get(field) not in (None, "", [], {}) for field in required)
                for run in runs
            )
        if not valid:
            _evidence_error(findings, goal_id, "feedback_result_invalid")
        return

    if goal_id == "HUMAN-001":
        review = _read_json_evidence(
            paths["review_record"], goal_id, "review_record", findings
        )
        duration = review.get("duration_minutes") if isinstance(review, dict) else None
        valid = isinstance(review, dict) and (
            review.get("schema") == "space_civilization_human_review.v1"
            and isinstance(duration, int)
            and not isinstance(duration, bool)
            and 15 <= duration <= 25
            and _positive_int(review.get("reviewer_count"))
            and review.get("comparison_completed") is True
            and review.get("model_causality_explained") is True
            and bool(review.get("review_findings"))
            and bool(review.get("reviewed_at"))
        )
        if not valid:
            _evidence_error(findings, goal_id, "human_review_result_invalid")
        return

    if goal_id == "CI-001":
        try:
            workflow = paths["workflow"].read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            workflow = ""
        workflow_tokens = (
            "jobs:",
            "goal-contract",
            "secret-scan",
            "ratchet",
            "ubuntu-latest",
            "windows-latest",
        )
        workflow_valid = all(token in workflow for token in workflow_tokens)
        receipt_data = _read_json_evidence(
            paths["ci_receipt"], goal_id, "ci_receipt", findings
        )
        try:
            inspected_head = head_resolver(repo)
        except (OSError, subprocess.SubprocessError, ValueError):
            inspected_head = ""
        expected_run_url = ""
        if isinstance(receipt_data, dict):
            run_url = receipt_data.get("run_url")
            match = re.fullmatch(
                rf"{re.escape(CANONICAL_REPOSITORY_URL)}/actions/runs/(?P<run_id>[1-9]\d*)",
                run_url if isinstance(run_url, str) else "",
            )
            if match:
                expected_run_url = (
                    f"{CANONICAL_REPOSITORY_URL}/actions/runs/{match.group('run_id')}"
                )
        valid = bool(inspected_head) and isinstance(receipt_data, dict) and (
            receipt_data.get("schema") == "space_civilization_ci_receipt.v1"
            and receipt_data.get("repository") == CANONICAL_REPOSITORY
            and receipt_data.get("head_sha") == inspected_head
            and receipt_data.get("conclusion") == "success"
            and isinstance(receipt_data.get("jobs"), dict)
            and all(
                receipt_data["jobs"].get(job) == "success"
                for job in REQUIRED_CI_JOBS
            )
            and receipt_data.get("run_url") == expected_run_url
        )
        if not workflow_valid or not valid:
            _evidence_error(findings, goal_id, "ci_result_invalid")
            return
        try:
            live = live_verifier(goal_id, receipt_data)
        except (OSError, ValueError, urllib.error.URLError):
            _evidence_error(findings, goal_id, "ci_live_readback_unavailable")
            return
        live_valid = isinstance(live, dict) and (
            live.get("repository") == CANONICAL_REPOSITORY
            and live.get("head_sha") == inspected_head
            and live.get("conclusion") == "success"
            and live.get("run_url") == expected_run_url
            and isinstance(live.get("jobs"), dict)
            and all(live["jobs"].get(job) == "success" for job in REQUIRED_CI_JOBS)
        )
        if not live_valid:
            _evidence_error(findings, goal_id, "ci_live_readback_mismatch")
        return

    if goal_id == "PUBLIC-001":
        try:
            checklist = paths["checklist"].read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            checklist = ""
        checklist_valid = "- [x]" in checklist.lower() and not re.search(
            r"^- \[ \]", checklist, re.MULTILINE
        )
        readback = _read_json_evidence(paths["readback"], goal_id, "readback", findings)
        public_files = ("README.md", "LICENSE", "SECURITY.md")
        local_files_valid = all(
            (repo / path).is_file() and (repo / path).stat().st_size > 0
            for path in public_files
        )
        try:
            inspected_head = head_resolver(repo)
        except (OSError, subprocess.SubprocessError, ValueError):
            inspected_head = ""
        try:
            personal_paths_clear, personal_path_matches = personal_path_scanner(repo)
        except (OSError, subprocess.SubprocessError, UnicodeError, ValueError):
            personal_paths_clear, personal_path_matches = False, []
        valid = bool(inspected_head) and isinstance(readback, dict) and (
            readback.get("schema") == "space_civilization_public_readback.v1"
            and readback.get("repository") == CANONICAL_REPOSITORY
            and readback.get("visibility") == "public"
            and readback.get("default_branch") == "main"
            and readback.get("head_sha") == inspected_head
            and readback.get("readback_url") == CANONICAL_REPOSITORY_URL
        )
        if not personal_paths_clear:
            _evidence_error(
                findings,
                goal_id,
                "tracked_personal_path_scan_failed",
                paths="|".join(personal_path_matches),
            )
        if not checklist_valid or not local_files_valid or not valid:
            _evidence_error(findings, goal_id, "public_readback_result_invalid")
            return
        if not personal_paths_clear:
            return
        try:
            live = live_verifier(goal_id, readback)
        except (OSError, ValueError, urllib.error.URLError):
            _evidence_error(findings, goal_id, "public_live_readback_unavailable")
            return
        live_valid = isinstance(live, dict) and (
            live.get("repository") == CANONICAL_REPOSITORY
            and live.get("visibility") == "public"
            and live.get("default_branch") == "main"
            and live.get("main_head") == inspected_head
            and live.get("repository_url") == CANONICAL_REPOSITORY_URL
            and isinstance(live.get("files"), dict)
            and all(live["files"].get(path) is True for path in public_files)
        )
        if not live_valid:
            _evidence_error(findings, goal_id, "public_live_readback_mismatch")


def _validate_done_when_evidence(
    repo: Path,
    goal_id: str,
    evidence_links: set[str],
    findings: list[dict[str, str]],
    live_verifier: LiveVerifier,
    head_resolver: HeadResolver,
    personal_path_scanner: PersonalPathScanner,
) -> None:
    """done_when固有の正本receiptと、その型付き一次証拠を検証する。"""
    contract = DONE_WHEN_EVIDENCE_CONTRACTS.get(goal_id)
    if contract is None:
        _evidence_error(findings, goal_id, "unknown_done_when_contract")
        return
    expected_target = f"evidence/done-when/{goal_id}.json"
    if expected_target not in evidence_links:
        _evidence_error(
            findings,
            goal_id,
            "canonical_receipt_missing",
            expected=expected_target,
            actual="|".join(sorted(evidence_links)),
        )
        return

    receipt_path = _resolved_link(repo, "PROJECT_GOAL.md", expected_target)
    if receipt_path is None or not receipt_path.is_file():
        _evidence_error(
            findings,
            goal_id,
            "canonical_receipt_unreadable",
            target=expected_target,
        )
        return

    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _evidence_error(
            findings,
            goal_id,
            "canonical_receipt_invalid_json",
            target=expected_target,
        )
        return
    if not isinstance(receipt, dict):
        _evidence_error(
            findings,
            goal_id,
            "canonical_receipt_not_object",
            target=expected_target,
        )
        return

    expected_fields = {
        "schema": DONE_WHEN_EVIDENCE_SCHEMA,
        "done_when_id": goal_id,
        "evidence_type": contract["evidence_type"],
        "status": "passed",
    }
    for field, expected in expected_fields.items():
        actual = receipt.get(field)
        if actual != expected:
            _evidence_error(
                findings,
                goal_id,
                "receipt_field_mismatch",
                field=field,
                expected=str(expected),
                actual=str(actual) if actual is not None else "",
            )

    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        _evidence_error(
            findings,
            goal_id,
            "artifacts_not_object",
            target=expected_target,
        )
        return
    artifact_hashes = receipt.get("artifact_sha256")
    if not isinstance(artifact_hashes, dict):
        _evidence_error(
            findings,
            goal_id,
            "artifact_hashes_not_object",
            target=expected_target,
        )
        return
    resolved_artifacts: dict[str, Path] = {}
    for role, pattern in contract["artifacts"].items():
        target = artifacts.get(role)
        if not isinstance(target, str) or not re.fullmatch(pattern, target):
            _evidence_error(
                findings,
                goal_id,
                "artifact_destination_mismatch",
                artifact_role=role,
                expected=pattern,
                actual=target if isinstance(target, str) else "",
            )
            continue
        resolved = _resolved_link(repo, expected_target, f"../../{target}")
        if resolved is None or not resolved.is_file():
            _evidence_error(
                findings,
                goal_id,
                "artifact_unreadable",
                artifact_role=role,
                target=target,
            )
            continue
        resolved_artifacts[role] = resolved
        actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
        expected_hash = artifact_hashes.get(role)
        if not _is_digest(expected_hash) or expected_hash != actual_hash:
            _evidence_error(
                findings,
                goal_id,
                "artifact_hash_mismatch",
                artifact_role=role,
                expected=actual_hash,
                actual=expected_hash if isinstance(expected_hash, str) else "",
            )

    if set(resolved_artifacts) == set(contract["artifacts"]):
        _validate_done_when_artifact_contents(
            goal_id,
            resolved_artifacts,
            receipt,
            findings,
            repo,
            live_verifier,
            head_resolver,
            personal_path_scanner,
        )


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        _content(text),
        re.MULTILINE | re.DOTALL,
    )
    return match.group("body") if match else ""


def _markdown_schema_rows(
    section: str,
) -> tuple[dict[str, tuple[str, ...]], set[str], list[int]]:
    rows: dict[str, tuple[str, ...]] = {}
    duplicates: set[str] = set()
    malformed_lines: list[int] = []
    for line_number, line in enumerate(section.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) == 3 and cells[0] == "field":
            continue
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        match = re.fullmatch(
            r"\|\s*`(?P<field>[^`]+)`\s*\|(?P<values>[^|]*)\|[^|]*\|",
            stripped,
        )
        if not match:
            malformed_lines.append(line_number)
            continue
        field = match.group("field")
        if field in rows:
            duplicates.add(field)
        rows[field] = tuple(re.findall(r"`([^`]+)`", match.group("values")))
    return rows, duplicates, malformed_lines


def _markdown_ssot_rows(
    section: str,
) -> tuple[dict[str, str], set[str], list[int]]:
    rows: dict[str, str] = {}
    duplicates: set[str] = set()
    malformed_lines: list[int] = []
    for line_number, line in enumerate(section.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) == 4 and cells[0] == "concern_id":
            continue
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        match = re.fullmatch(
            r"\|\s*`(?P<concern_id>[a-z][a-z0-9_]*)`\s*\|[^|]*\|\s*"
            r"\[[^]]+\]\((?P<target>[^)]+)\)\s*\|[^|]*\|",
            stripped,
        )
        if not match:
            malformed_lines.append(line_number)
            continue
        concern_id = match.group("concern_id")
        if concern_id in rows:
            duplicates.add(concern_id)
        rows[concern_id] = match.group("target")
    return rows, duplicates, malformed_lines


def build_report(
    repo: Path,
    *,
    live_verifier: LiveVerifier | None = None,
    head_resolver: HeadResolver | None = None,
    personal_path_scanner: PersonalPathScanner | None = None,
) -> dict[str, Any]:
    repo = repo.resolve()
    live_verifier = live_verifier or _default_live_verifier
    head_resolver = head_resolver or _resolve_git_head
    personal_path_scanner = personal_path_scanner or _scan_tracked_personal_paths
    findings: list[dict[str, str]] = []

    for relative in REQUIRED_FILES:
        if not (repo / relative).is_file():
            _finding(findings, "missing_file", path=relative)

    documents = {
        relative: _read(repo, relative)
        for relative in REQUIRED_FILES
        if (repo / relative).is_file()
    }
    for relative, text in documents.items():
        without_front_matter = FRONT_MATTER_RE.sub("", text, count=1)
        _, unterminated_fence, unterminated_comment = _strip_fenced_blocks(
            without_front_matter
        )
        if unterminated_fence:
            _finding(findings, "unterminated_code_fence", path=relative)
        if unterminated_comment:
            _finding(findings, "unterminated_html_comment", path=relative)

    goal_text = documents.get("PROJECT_GOAL.md", "")
    goal_meta = _front_matter(goal_text)
    expected_goal_meta = {
        "type": "project-goal",
        "owner": OWNER,
        "project": "space-civilization-choice",
        "canonical_repository": "nexus-ai-2045/space-civilization-choice",
        "goal_id": GOAL_ID,
    }
    for key, expected in expected_goal_meta.items():
        actual = goal_meta.get(key)
        if actual != expected:
            _finding(
                findings,
                "goal_metadata_mismatch",
                field=key,
                expected=expected,
                actual=actual or "",
            )

    status = goal_meta.get("status", "")
    if status not in GOAL_STATUSES:
        _finding(
            findings,
            "invalid_goal_status",
            expected="|".join(sorted(GOAL_STATUSES)),
            actual=status,
        )

    displayed_status_matches = re.findall(
        r"^-\s+`status`:\s*(?P<status>[a-z]+)\s*$",
        _section(goal_text, "現在の達成状態"),
        re.MULTILINE,
    )
    if not displayed_status_matches:
        _finding(findings, "current_status_missing", expected=status)
    elif len(displayed_status_matches) > 1:
        _finding(
            findings,
            "current_status_duplicate",
            actual="|".join(displayed_status_matches),
        )
    elif displayed_status_matches[0] != status:
        _finding(
            findings,
            "current_status_mismatch",
            expected=status,
            actual=displayed_status_matches[0],
        )

    headings = set(HEADING_RE.findall(_content(goal_text)))
    for heading in REQUIRED_GOAL_HEADINGS:
        if heading not in headings:
            _finding(findings, "missing_goal_heading", value=heading)

    checkboxes = list(CHECKBOX_RE.finditer(_content(goal_text)))
    by_id: dict[str, list[re.Match[str]]] = {}
    for checkbox in checkboxes:
        by_id.setdefault(checkbox.group("id"), []).append(checkbox)
    for goal_id in DONE_WHEN_IDS:
        matches = by_id.get(goal_id, [])
        if not matches:
            _finding(findings, "missing_done_when", value=goal_id)
        elif len(matches) > 1:
            _finding(findings, "duplicate_done_when", value=goal_id)
    for unknown_id in sorted(set(by_id) - set(DONE_WHEN_IDS)):
        _finding(findings, "unknown_done_when", value=unknown_id)

    checked_ids = {
        goal_id
        for goal_id, matches in by_id.items()
        if len(matches) == 1 and matches[0].group("checked").lower() == "x"
    }
    validated_done_when_ids: set[str] = set()
    for goal_id in sorted(checked_ids):
        body = by_id[goal_id][0].group("body")
        evidence_links = _markdown_links(body)
        if not evidence_links:
            _finding(findings, "checked_without_evidence", value=goal_id)
            continue
        if goal_id == "PUBLIC-001":
            missing_dependencies = sorted(
                {"CI-001", "HUMAN-001"} - validated_done_when_ids
            )
            if missing_dependencies:
                _evidence_error(
                    findings,
                    goal_id,
                    "public_dependency_unvalidated",
                    missing="|".join(missing_dependencies),
                )
                continue
        finding_count = len(findings)
        _validate_done_when_evidence(
            repo,
            goal_id,
            evidence_links,
            findings,
            live_verifier,
            head_resolver,
            personal_path_scanner,
        )
        if len(findings) == finding_count:
            validated_done_when_ids.add(goal_id)

    all_complete = checked_ids == set(DONE_WHEN_IDS)
    if status == "design" and checked_ids:
        _finding(
            findings,
            "design_status_has_completed_items",
            actual=str(len(checked_ids)),
        )
    if status == "complete" and not all_complete:
        _finding(
            findings,
            "complete_status_has_open_items",
            actual=str(len(checked_ids)),
        )
    if status != "complete" and all_complete:
        _finding(findings, "all_items_complete_but_status_open", actual=status)

    product_meta = _front_matter(documents.get("docs/PRODUCT_SPEC.md", ""))
    expected_product_meta = {
        "type": "product-spec",
        "status": status,
        "owner": OWNER,
        "goal_id": GOAL_ID,
    }
    for key, expected in expected_product_meta.items():
        actual = product_meta.get(key)
        if actual != expected:
            _finding(
                findings,
                "product_metadata_mismatch",
                field=key,
                expected=expected,
                actual=actual or "",
            )

    ssot_text = documents.get("PROJECT_SSOT.md", "")
    ssot_meta = _front_matter(ssot_text)
    for key, expected in {
        "type": "project-ssot",
        "status": "active",
        "owner": OWNER,
        "canonical_repository": "nexus-ai-2045/space-civilization-choice",
    }.items():
        actual = ssot_meta.get(key)
        if actual != expected:
            _finding(
                findings,
                "ssot_metadata_mismatch",
                field=key,
                expected=expected,
                actual=actual or "",
            )
    ssot_headings = set(HEADING_RE.findall(_content(ssot_text)))
    for heading in (
        "正本マップ",
        "正本ではないもの",
        "ローカル配置境界",
        "変更ルール",
        "保証と限界",
    ):
        if heading not in ssot_headings:
            _finding(findings, "ssot_heading_missing", value=heading)

    ssot_rows, duplicate_ssot_rows, malformed_ssot_lines = _markdown_ssot_rows(
        _section(ssot_text, "正本マップ")
    )
    for line_number in malformed_ssot_lines:
        _finding(
            findings,
            "ssot_row_malformed",
            section_line=str(line_number),
        )
    for concern_id in sorted(duplicate_ssot_rows):
        _finding(findings, "ssot_row_duplicate", concern_id=concern_id)
    for concern_id in sorted(set(ssot_rows) - set(SSOT_CANONICAL_ROWS)):
        _finding(findings, "ssot_concern_unexpected", concern_id=concern_id)
    for concern_id, expected_target in SSOT_CANONICAL_ROWS.items():
        actual_target = ssot_rows.get(concern_id)
        if actual_target is None:
            _finding(findings, "ssot_concern_missing", concern_id=concern_id)
        elif actual_target != expected_target:
            _finding(
                findings,
                "ssot_target_mismatch",
                concern_id=concern_id,
                expected=expected_target,
                actual=actual_target,
            )

    readme = _content(documents.get("README.md", ""))
    for field, expected in {"goal ID": GOAL_ID, "owner": OWNER}.items():
        pattern = re.compile(
            rf"^- {re.escape(field)}: `{re.escape(expected)}`\s*$",
            re.MULTILINE,
        )
        if not pattern.search(readme):
            _finding(
                findings,
                "readme_governance_mismatch",
                field=field,
                expected=expected,
            )
    for heading in ("目的", "制約"):
        if heading not in set(HEADING_RE.findall(readme)):
            _finding(findings, "readme_scope_heading_missing", value=heading)

    for adr_path, required_terms in ADR_CONTRACTS.items():
        adr = documents.get(adr_path, "")
        adr_meta = _front_matter(adr)
        for key, expected in {
            "type": "adr",
            "status": "accepted",
            "owner": OWNER,
        }.items():
            actual = adr_meta.get(key)
            if actual != expected:
                _finding(
                    findings,
                    "adr_metadata_mismatch",
                    path=adr_path,
                    field=key,
                    expected=expected,
                    actual=actual or "",
                )
        adr_content = _content(adr)
        adr_headings = set(HEADING_RE.findall(adr_content))
        for heading in (
            "Context",
            "Decision",
            "Allowed",
            "Prohibited",
            "Human Review Gate",
            "Consequences",
            "Review Evidence",
            "Next Actions",
        ):
            if heading not in adr_headings:
                _finding(
                    findings,
                    "adr_heading_missing",
                    path=adr_path,
                    value=heading,
                )
        for term in required_terms:
            if term not in adr_content:
                _finding(
                    findings,
                    "adr_contract_term_missing",
                    path=adr_path,
                    value=term,
                )

    schema_adr_path = "docs/adr/0006-separate-epistemic-provenance-validation.md"
    schema_adr = documents.get(schema_adr_path, "")
    schema_rows, duplicate_schema_fields, malformed_schema_lines = (
        _markdown_schema_rows(_section(schema_adr, "Decision"))
    )
    for line_number in malformed_schema_lines:
        _finding(
            findings,
            "adr_schema_row_malformed",
            path=schema_adr_path,
            section_line=str(line_number),
        )
    for field in sorted(duplicate_schema_fields):
        _finding(
            findings,
            "adr_schema_row_duplicate",
            path=schema_adr_path,
            field=field,
        )
    for field in sorted(set(schema_rows) - set(ADR_SCHEMA_ROWS)):
        _finding(
            findings,
            "adr_schema_field_unexpected",
            path=schema_adr_path,
            field=field,
        )
    for field, expected_values in ADR_SCHEMA_ROWS.items():
        actual_values = schema_rows.get(field)
        if actual_values is None:
            _finding(
                findings,
                "adr_schema_row_missing",
                path=schema_adr_path,
                field=field,
            )
        elif actual_values != expected_values:
            _finding(
                findings,
                "adr_schema_values_mismatch",
                path=schema_adr_path,
                field=field,
                expected="|".join(expected_values),
                actual="|".join(actual_values),
            )

    for relative, required_targets in REQUIRED_LINKS.items():
        text = documents.get(relative)
        if text is None:
            continue
        links = _markdown_links(text)
        for target in required_targets:
            if target not in links:
                _finding(
                    findings,
                    "missing_contract_link",
                    path=relative,
                    value=target,
                )
                continue
            resolved = _resolved_link(repo, relative, target)
            if resolved is None or not resolved.is_file():
                _finding(
                    findings,
                    "broken_contract_link",
                    path=relative,
                    value=target,
                )

    contract_valid = not findings
    product_mvp_complete = contract_valid and status == "complete" and all_complete
    if not contract_valid:
        state = "blocked"
    elif product_mvp_complete:
        state = "contract_valid_product_complete"
    else:
        state = "contract_valid_product_incomplete"
    return {
        "schema": "space_civilization_project_goal_check.v3",
        "contract_valid": contract_valid,
        "state": state,
        "goal_status": status,
        "product_mvp_complete": product_mvp_complete,
        "checked_done_when_ids": sorted(checked_ids),
        "checked_files": list(REQUIRED_FILES),
        "done_when_ids": list(DONE_WHEN_IDS),
        "findings": findings,
        "external_actions_performed": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="project goal contractを検査する。")
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
        print(f"contract_valid: {str(report['contract_valid']).lower()}")
        print(f"product_mvp_complete: {str(report['product_mvp_complete']).lower()}")
        for finding in report["findings"]:
            print(f"- {finding}")
    return 0 if report["contract_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
