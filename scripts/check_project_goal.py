#!/usr/bin/env python3
"""Project goal contract の構造、文書間整合、状態遷移を検査する。"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
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
    "ops/adoption-manifest.json",
    "docs/adr/0005-adaptive-exploratory-decision-loop.md",
    "docs/adr/0006-separate-epistemic-provenance-validation.md",
    "docs/adr/0007-operational-adoption-contract.md",
    "docs/adr/README.md",
)

GOAL_ID = "space-civilization-choice-mvp-v1"
OWNER = "repository-maintainers"
GOAL_STATUSES = {"design", "active", "complete"}
CANONICAL_REPOSITORY = "nexus-ai-2045/space-civilization-choice"
CANONICAL_REPOSITORY_URL = f"https://github.com/{CANONICAL_REPOSITORY}"
REQUIRED_CI_JOBS = (
    "secret-scan",
    "goal-contract (ubuntu-latest)",
    "goal-contract (windows-latest)",
    "ratchet (ubuntu-latest)",
    "ratchet (windows-latest)",
)
CI_EXACT_HEAD_VERIFIER_JOB = "ci-exact-head-verifier"
RULESET_REQUIRED_CHECKS = (*REQUIRED_CI_JOBS, CI_EXACT_HEAD_VERIFIER_JOB)
ACTIVE_MAIN_RULESET_ID = 21258820
GITHUB_ACTIONS_APP_ID = 15368
CANONICAL_TRACE_AXES = frozenset(
    {
        "access_and_operation",
        "industrial_reproduction",
        "rule_shaping",
        "knowledge_continuity",
        "relationship_choice",
        "public_legitimacy",
    }
)
CANONICAL_BRANCH_IDS = frozenset(
    {"international_integration", "domestic_autonomy", "open_platform"}
)
PHASE1_TRACE_TURN_IDS = (1, 2, 3, 4)
PHASE1_ACTION_RULES = {
    "allocate_to_domestic_core_components": "R-DOM-01",
    "qualify_redundant_component_supply": "R-DOM-02",
    "expand_maintainer_training": "R-DOM-03",
    "operate_with_domestic_maintenance_chain": "R-DOM-04",
}
LiveVerifier = Callable[[str, dict[str, Any]], dict[str, Any]]
HeadResolver = Callable[[Path], str]
PersonalPathScanner = Callable[[Path], tuple[bool, list[str]]]
RulesetReader = Callable[[], frozenset[str]]

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
            "fixture": r"^fixtures/.+\.json$",
            "run_manifest": r"^(?:evidence|artifacts)/runs/.+\.json$",
            "canonical_manifest": r"^(?:evidence|artifacts)/runs/.+/run-manifest\.json$",
            "event_log": r"^(?:evidence|artifacts)/runs/.+/events\.jsonl$",
        },
    },
    "BRANCH-001": {
        "evidence_type": "common_branch_inputs",
        "artifacts": {
            "test": r"^tests/.+\.py$",
            "run_manifest": r"^(?:evidence|artifacts)/runs/.+\.json$",
            "event_log_international_integration": (
                r"^(?:evidence|artifacts)/runs/.+/events\.jsonl$"
            ),
            "event_log_domestic_autonomy": (
                r"^(?:evidence|artifacts)/runs/.+/events\.jsonl$"
            ),
            "event_log_open_platform": r"^(?:evidence|artifacts)/runs/.+/events\.jsonl$",
        },
    },
    "TRACE-001": {
        "evidence_type": "transition_trace",
        "artifacts": {
            "test": r"^tests/.+\.py$",
            "trace": r"^(?:evidence|artifacts)/runs/.+\.jsonl?$",
            "source_manifest": r"^(?:evidence|artifacts)/runs/.+/run-manifest\.json$",
            "event_log": r"^(?:evidence|artifacts)/runs/.+/events\.jsonl$",
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
        "ops/adoption-manifest.json",
        "PUBLIC_READY.md",
    ),
    "docs/ROADMAP.md": ("../PROJECT_GOAL.md",),
    "docs/adr/README.md": (
        "0005-adaptive-exploratory-decision-loop.md",
        "0006-separate-epistemic-provenance-validation.md",
        "0007-operational-adoption-contract.md",
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
    "docs/adr/0007-operational-adoption-contract.md": (
        "space-civilization-operational-adoption/v1",
        "enforced_ci",
        "operator_gate",
        "design_reference",
        "future_candidate",
        "out_of_scope",
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
    "operational_adoption": "ops/adoption-manifest.json",
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


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _simulation_api():
    """goal gateから決定論的coreを読み、fixture再実行とdraw再計算に使う。"""
    root = Path(__file__).resolve().parents[1]
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import space_civilization.simulation as simulation

    return simulation


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


def _git_is_ancestor(repo: Path, maybe_ancestor: str, head: str) -> bool:
    """maybe_ancestor が head と同一、またはその祖先なら True。"""
    if maybe_ancestor == head:
        return True
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "merge-base",
            "--is-ancestor",
            maybe_ancestor,
            head,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.returncode == 0


def _scan_tracked_personal_paths(repo: Path) -> tuple[bool, list[str]]:
    """cleanなHEADのtracked textだけを上限付きで直接走査する。"""
    # Windows runners may expose the temp root through an 8.3 short path while
    # child.resolve() expands it. Compare canonical forms to avoid a false escape.
    canonical_repo = repo.resolve()
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
        candidate = (canonical_repo / relative).resolve()
        try:
            candidate.relative_to(canonical_repo)
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


def _reject_nonstandard_json_constant(value: str) -> None:
    """Python jsonのNaN/Infinity拡張を拒否し、標準JSONへfail-closedする。"""
    raise ValueError(f"non-standard JSON constant: {value}")


def _loads_strict_json(text: str) -> Any:
    return json.loads(text, parse_constant=_reject_nonstandard_json_constant)


def _read_jsonl_objects(path: Path) -> list[Any]:
    return [
        _loads_strict_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _github_json(api_path: str) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "space-civilization-choice-goal-gate",
    }
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    request = urllib.request.Request(
        f"https://api.github.com{api_path}",
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("GitHub API response is not an object")
    return payload


def _ruleset_required_contexts(payload: dict[str, Any]) -> frozenset[str]:
    contexts: set[str] = set()
    rules = payload.get("rules")
    if not isinstance(rules, list):
        return frozenset()
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
            continue
        parameters = rule.get("parameters")
        if not isinstance(parameters, dict):
            continue
        checks = parameters.get("required_status_checks")
        if not isinstance(checks, list):
            continue
        for check in checks:
            if not isinstance(check, dict):
                continue
            context = check.get("context")
            if isinstance(context, str) and context:
                contexts.add(context)
    return frozenset(contexts)


def _default_ruleset_reader() -> frozenset[str]:
    payload = _github_json(
        f"/repos/{CANONICAL_REPOSITORY}/rulesets/{ACTIVE_MAIN_RULESET_ID}"
    )
    return _ruleset_required_contexts(payload)


def _default_live_verifier(
    goal_id: str, evidence: dict[str, Any]
) -> dict[str, Any]:
    """CI/PUBLICの自己申告をGitHub公開APIでread-backする。"""
    if goal_id == "CI-001":
        # inspected HEADはGitから得た値を優先する。同一commit内receiptへSHAを埋め込まない。
        inspected_head = evidence.get("inspected_head")
        if not isinstance(inspected_head, str) or not _is_digest(
            inspected_head.lower(), length=40
        ):
            raise ValueError("inspected HEAD is missing")
        inspected_head = inspected_head.lower()
        checks_payload = _github_json(
            f"/repos/{CANONICAL_REPOSITORY}/commits/{inspected_head}/check-runs?per_page=100"
        )
        check_runs = checks_payload.get("check_runs")
        jobs: dict[str, Any] = {}
        if isinstance(check_runs, list):
            for check in check_runs:
                if not isinstance(check, dict):
                    continue
                name = check.get("name")
                if not isinstance(name, str):
                    continue
                conclusion = check.get("conclusion")
                # 同名checkが複数ある場合はsuccessを優先して残す。
                if name not in jobs or conclusion == "success":
                    jobs[name] = conclusion
        all_required_ok = all(jobs.get(job) == "success" for job in REQUIRED_CI_JOBS)
        terminal_failure = any(
            conclusion in {"failure", "cancelled", "timed_out", "action_required"}
            for conclusion in jobs.values()
        )
        return {
            "repository": CANONICAL_REPOSITORY,
            "head_sha": inspected_head,
            "conclusion": (
                "success" if all_required_ok else "failure" if terminal_failure else "pending"
            ),
            "jobs": jobs,
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
        return _loads_strict_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
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
    ruleset_reader: RulesetReader,
    verify_ci_live: bool,
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
        replay_output: str | None = None
        replay_signature: tuple[str, str, int, str] | None = None
        if valid:
            signatures: set[tuple[str, str, int, str]] = set()
            outputs: set[str] = set()
            for run in replays:
                if not isinstance(run, dict):
                    valid = False
                    break
                snapshot = run.get("scenario_snapshot_hash")
                execution_input = run.get("deterministic_execution_input_hash")
                seed = run.get("seed")
                model_version = run.get("model_version")
                # setへ入れる前にhash可能な正規形へ落とす。不正値はTypeErrorにせず証拠無効にする。
                if not _is_digest(snapshot) or not _is_digest(execution_input):
                    valid = False
                    break
                if type(seed) is not int:
                    valid = False
                    break
                if not isinstance(model_version, str) or not model_version:
                    valid = False
                    break
                signatures.add((snapshot, execution_input, seed, model_version))
                output_hash = run.get("canonical_output_hash")
                if not _is_digest(output_hash):
                    valid = False
                else:
                    outputs.add(output_hash)
            valid = valid and len(signatures) == 1 and len(outputs) == 1
            if valid:
                replay_output = next(iter(outputs))
                replay_signature = next(iter(signatures))
        if not valid:
            _evidence_error(findings, goal_id, "replay_result_invalid")
            return
        stored = _read_json_evidence(paths["canonical_manifest"], goal_id, "canonical_manifest", findings)
        try:
            events = _read_jsonl_objects(paths["event_log"])
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            _evidence_error(findings, goal_id, "event_log_invalid_jsonl")
            return
        receipt_result = receipt.get("result")
        receipt_hash = (
            receipt_result.get("canonical_output_hash")
            if isinstance(receipt_result, dict)
            else None
        )
        stored_valid = isinstance(stored, dict)
        stored_valid = stored_valid and stored.get("schema") == "space_civilization_stored_run.v1"
        stored_valid = stored_valid and stored.get("event_count") == len(events) and len(events) > 0
        canonical_result = stored.get("canonical_result") if isinstance(stored, dict) else None
        try:
            computed_event_hash = _sha256_json(events)
            computed_output_hash = (
                _sha256_json(canonical_result)
                if isinstance(canonical_result, dict)
                else None
            )
        except (TypeError, ValueError, OverflowError):
            computed_event_hash = None
            computed_output_hash = None
            stored_valid = False
        stored_valid = stored_valid and stored.get("event_log_hash") == computed_event_hash
        # copied digest同士の一致ではなく、永続化された完全resultから再計算する。
        stored_valid = stored_valid and computed_output_hash == replay_output
        stored_valid = stored_valid and stored.get("canonical_output_hash") == computed_output_hash
        stored_valid = stored_valid and receipt_hash == computed_output_hash
        persisted_manifest: dict[str, Any] | None = None
        if isinstance(canonical_result, dict):
            stored_valid = stored_valid and canonical_result.get("events") == events
            stored_valid = stored_valid and canonical_result.get("event_log_hash") == computed_event_hash
            maybe_manifest = canonical_result.get("manifest")
            # replay署名は永続化されたresult.manifestへ束縛する。
            stored_valid = stored_valid and isinstance(maybe_manifest, dict)
            stored_valid = stored_valid and replay_signature is not None
            if stored_valid and isinstance(maybe_manifest, dict) and replay_signature is not None:
                persisted_manifest = maybe_manifest
                stored_valid = (
                    maybe_manifest.get("scenario_snapshot_hash") == replay_signature[0]
                    and maybe_manifest.get("deterministic_execution_input_hash")
                    == replay_signature[1]
                    and stored.get("deterministic_execution_input_hash") == replay_signature[1]
                    and maybe_manifest.get("seed") == replay_signature[2]
                    and maybe_manifest.get("model_version") == replay_signature[3]
                )
        else:
            stored_valid = False
        # fixtureそのものからexecution hashとoutputを再計算し、copied digestだけの証明を拒否する。
        if stored_valid and replay_signature is not None:
            try:
                simulation = _simulation_api()
                fixture = simulation.load_fixture(paths["fixture"])
                live_result = simulation.run_simulation(fixture)
            except (
                OSError,
                UnicodeError,
                ValueError,
                TypeError,
                AttributeError,
                OverflowError,
                ImportError,
                ModuleNotFoundError,
            ):
                stored_valid = False
            else:
                stored_valid = (
                    simulation.sha256_json(fixture) == replay_signature[1]
                    and live_result["manifest"]["deterministic_execution_input_hash"]
                    == replay_signature[1]
                    and live_result["canonical_output_hash"] == computed_output_hash
                    and live_result["events"] == events
                )
        if stored_valid and isinstance(persisted_manifest, dict):
            previous_after: dict[str, int] | None = None
            seed = persisted_manifest.get("seed")
            for event in events:
                if not isinstance(event, dict):
                    stored_valid = False
                    break
                before = event.get("before")
                after = event.get("after")
                deltas = event.get("axis_deltas")
                base_deltas = event.get("base_axis_deltas")
                exogenous = event.get("exogenous_effect")
                random_draw = event.get("random_draw")
                event_input = event.get("input")
                year = event.get("year")
                action = event.get("action")
                rule_id = event.get("rule_id")
                if not all(
                    isinstance(value, dict)
                    for value in (before, after, deltas, base_deltas, exogenous, event_input)
                ):
                    stored_valid = False
                    break
                if (
                    set(before) != CANONICAL_TRACE_AXES
                    or set(after) != CANONICAL_TRACE_AXES
                    or set(deltas) != CANONICAL_TRACE_AXES
                    or set(base_deltas) != CANONICAL_TRACE_AXES
                ):
                    stored_valid = False
                    break
                if PHASE1_ACTION_RULES.get(action) != rule_id:
                    stored_valid = False
                    break
                input_event = event_input.get("exogenous_event")
                effect_axis = exogenous.get("axis")
                modifier = exogenous.get("modifier")
                provenance = exogenous.get("provenance")
                if (
                    not isinstance(input_event, str)
                    or provenance != input_event
                    or type(seed) is not int
                    or type(year) is not int
                    or type(random_draw) not in (int, float)
                    or isinstance(random_draw, bool)
                ):
                    stored_valid = False
                    break
                try:
                    simulation = _simulation_api()
                    expected_draw = simulation.deterministic_draw(seed, year, input_event)
                    expected_effect = simulation.realize_exogenous_effect(
                        input_event, expected_draw
                    )
                except (
                    ValueError,
                    TypeError,
                    OverflowError,
                    KeyError,
                    ImportError,
                    ModuleNotFoundError,
                ):
                    stored_valid = False
                    break
                if (
                    random_draw != expected_draw
                    or effect_axis != expected_effect["axis"]
                    or modifier != expected_effect["modifier"]
                ):
                    stored_valid = False
                    break
                for axis in CANONICAL_TRACE_AXES:
                    value = before[axis]
                    delta = deltas[axis]
                    base_delta = base_deltas[axis]
                    after_value = after[axis]
                    if not all(
                        type(item) is int
                        for item in (value, delta, base_delta, after_value)
                    ):
                        stored_valid = False
                        break
                    expected_delta = base_delta + (
                        modifier if axis == effect_axis else 0
                    )
                    if delta != expected_delta or value + delta != after_value:
                        stored_valid = False
                        break
                if not stored_valid:
                    break
                # 隣接eventの連続性: events[n].after == events[n+1].before
                if previous_after is not None and before != previous_after:
                    stored_valid = False
                    break
                previous_after = after
            if stored_valid:
                final_state = canonical_result.get("final_state")
                final_axes = (
                    final_state.get("axes") if isinstance(final_state, dict) else None
                )
                # 最終event.afterはcanonical_result.final_state.axesへ束縛する。
                stored_valid = previous_after is not None and final_axes == previous_after
        if not stored_valid:
            _evidence_error(findings, goal_id, "stored_run_artifacts_invalid")
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
            common_inputs: set[tuple[str, int, str, str]] = set()
            event_log_hashes: set[str] = set()
            for branch in branches:
                if not isinstance(branch, dict) or not isinstance(
                    branch.get("branch_id"), str
                ):
                    valid = False
                    break
                branch_id = branch["branch_id"]
                snapshot = branch.get("scenario_snapshot_hash")
                seed = branch.get("seed")
                model_version = branch.get("model_version")
                stream_hash = branch.get("exogenous_event_stream_hash")
                event_log_hash = branch.get("event_log_hash")
                # set挿入前にhash可能な正規形へ落とす。
                if not _is_digest(snapshot) or not _is_digest(stream_hash):
                    valid = False
                    break
                if type(seed) is not int:
                    valid = False
                    break
                if not isinstance(model_version, str) or not model_version:
                    valid = False
                    break
                if not _is_digest(event_log_hash):
                    valid = False
                    break
                log_role = f"event_log_{branch_id}"
                log_path = paths.get(log_role)
                if log_path is None:
                    valid = False
                    break
                try:
                    events = _read_jsonl_objects(log_path)
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                    valid = False
                    break
                if not events or _sha256_json(events) != event_log_hash:
                    valid = False
                    break
                branch_ids.add(branch_id)
                common_inputs.add((snapshot, seed, model_version, stream_hash))
                event_log_hashes.add(event_log_hash)
            valid = valid and branch_ids == CANONICAL_BRANCH_IDS and len(common_inputs) == 1
            valid = valid and len(event_log_hashes) == 3
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
        source_manifest = _read_json_evidence(
            paths["source_manifest"], goal_id, "source_manifest", findings
        )
        if trace_path.suffix == ".jsonl":
            try:
                records = _read_jsonl_objects(trace_path)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                records = None
        else:
            payload = _read_json_evidence(trace_path, goal_id, "trace", findings)
            records = payload.get("records") if isinstance(payload, dict) else payload
        try:
            events = _read_jsonl_objects(paths["event_log"])
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            _evidence_error(findings, goal_id, "event_log_invalid_jsonl")
            return
        receipt_result = receipt.get("result")
        declared_count = (
            receipt_result.get("record_count")
            if isinstance(receipt_result, dict)
            else None
        )
        valid = isinstance(records, list) and bool(records)
        valid = valid and isinstance(source_manifest, dict)
        valid = valid and type(declared_count) is int and declared_count == len(records)
        valid = valid and declared_count == len(PHASE1_TRACE_TURN_IDS)
        valid = valid and len(events) == declared_count
        valid = valid and source_manifest.get("event_count") == len(events)
        valid = valid and source_manifest.get("event_log_hash") == _sha256_json(events)
        required = ("turn_id", "inputs", "action", "model_rule", "evidence_refs")
        if valid:
            turn_ids = [record.get("turn_id") for record in records if isinstance(record, dict)]
            valid = turn_ids == list(PHASE1_TRACE_TURN_IDS)
        if valid:
            for record in records:
                valid = isinstance(record, dict) and all(
                    record.get(field) not in (None, "", [], {}) for field in required
                )
                valid = valid and record.get("causal_scope") == "model_internal"
                axis_deltas = record.get("axis_deltas")
                base_deltas = record.get("base_axis_deltas")
                exogenous = record.get("exogenous_effect")
                random_draw = record.get("random_draw")
                valid = valid and isinstance(axis_deltas, dict)
                valid = valid and set(axis_deltas) == CANONICAL_TRACE_AXES
                valid = valid and all(type(delta) is int for delta in axis_deltas.values())
                valid = valid and isinstance(base_deltas, dict)
                valid = valid and set(base_deltas) == CANONICAL_TRACE_AXES
                valid = valid and all(type(delta) is int for delta in base_deltas.values())
                valid = valid and isinstance(exogenous, dict)
                exogenous_axis = exogenous.get("axis") if isinstance(exogenous, dict) else None
                exogenous_modifier = (
                    exogenous.get("modifier") if isinstance(exogenous, dict) else None
                )
                exogenous_provenance = (
                    exogenous.get("provenance") if isinstance(exogenous, dict) else None
                )
                valid = valid and isinstance(exogenous_axis, str)
                valid = valid and exogenous_axis in CANONICAL_TRACE_AXES
                valid = valid and type(exogenous_modifier) is int
                valid = (
                    valid
                    and isinstance(exogenous_provenance, str)
                    and bool(exogenous_provenance.strip())
                )
                valid = valid and isinstance(random_draw, (int, float))
                valid = valid and not isinstance(random_draw, bool)
                # float()変換は巨大整数でOverflowErrorになるため、直接比較する。
                valid = valid and 0 <= random_draw < 1
                if valid and isinstance(base_deltas, dict) and isinstance(exogenous, dict):
                    expected = dict(base_deltas)
                    expected[exogenous_axis] = (
                        expected[exogenous_axis] + exogenous_modifier
                    )
                    valid = axis_deltas == expected
                if not valid:
                    break
        if valid:
            try:
                simulation = _simulation_api()
                projected = simulation.build_model_internal_trace(events)
            except (ValueError, KeyError, TypeError, ImportError, ModuleNotFoundError):
                valid = False
            else:
                # traceは同一runのevent投影そのものへ束縛する。
                valid = records == projected
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
        receipt_head = ""
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
            raw_head = receipt_data.get("head_sha")
            if isinstance(raw_head, str):
                receipt_head = raw_head.lower()
        # receiptのhead_shaは履歴記録に留め、inspected HEADとの一致は要求しない。
        # exact HEAD束縛はGit由来のinspected_headに対するlive check-runsで行う。
        receipt_struct_valid = bool(inspected_head) and isinstance(receipt_data, dict) and (
            receipt_data.get("schema") == "space_civilization_ci_receipt.v1"
            and receipt_data.get("repository") == CANONICAL_REPOSITORY
            and _is_digest(receipt_head, length=40)
            and receipt_data.get("head_sha").lower() == receipt_head
            and receipt_data.get("conclusion") == "success"
            and isinstance(receipt_data.get("jobs"), dict)
            and all(
                receipt_data["jobs"].get(job) == "success"
                for job in REQUIRED_CI_JOBS
            )
            and receipt_data.get("run_url") == expected_run_url
        )
        if not workflow_valid or not receipt_struct_valid:
            _evidence_error(findings, goal_id, "ci_result_invalid")
            return
        if not verify_ci_live:
            return
        try:
            live = live_verifier(
                goal_id,
                {
                    **receipt_data,
                    "inspected_head": inspected_head,
                },
            )
        except (OSError, ValueError, urllib.error.URLError):
            _evidence_error(findings, goal_id, "ci_live_readback_unavailable")
            return
        live_valid = isinstance(live, dict) and (
            live.get("repository") == CANONICAL_REPOSITORY
            and isinstance(live.get("head_sha"), str)
            and live.get("head_sha").lower() == inspected_head
            and live.get("conclusion") == "success"
            and isinstance(live.get("jobs"), dict)
            and all(live["jobs"].get(job) == "success" for job in REQUIRED_CI_JOBS)
        )
        if not live_valid:
            _evidence_error(findings, goal_id, "ci_live_readback_mismatch")
            return
        try:
            ruleset_contexts = ruleset_reader()
        except (OSError, ValueError, urllib.error.URLError):
            _evidence_error(findings, goal_id, "ci_ruleset_readback_unavailable")
            return
        if not set(RULESET_REQUIRED_CHECKS).issubset(ruleset_contexts):
            _evidence_error(
                findings,
                goal_id,
                "ci_ruleset_required_checks_mismatch",
                expected="|".join(RULESET_REQUIRED_CHECKS),
                actual="|".join(sorted(ruleset_contexts)),
            )
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
    ruleset_reader: RulesetReader,
    verify_ci_live: bool,
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
        receipt = _loads_strict_json(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
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
        # Evidence hashes describe canonical repository text, not a platform's
        # checkout newline convention. All registered artifacts are UTF-8 text;
        # normalize CRLF/CR so the same exact HEAD verifies on Windows and Linux.
        artifact_bytes = resolved.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        actual_hash = hashlib.sha256(artifact_bytes).hexdigest()
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
            ruleset_reader,
            verify_ci_live,
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
    ruleset_reader: RulesetReader | None = None,
    verify_ci_live: bool = True,
) -> dict[str, Any]:
    repo = repo.resolve()
    live_verifier = live_verifier or _default_live_verifier
    head_resolver = head_resolver or _resolve_git_head
    personal_path_scanner = personal_path_scanner or _scan_tracked_personal_paths
    ruleset_reader = ruleset_reader or _default_ruleset_reader
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
            ruleset_reader,
            verify_ci_live,
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


def build_ci_exact_head_report(
    repo: Path,
    *,
    live_verifier: LiveVerifier | None = None,
    head_resolver: HeadResolver | None = None,
    ruleset_reader: RulesetReader | None = None,
) -> dict[str, Any]:
    """完了済みCIを外側から検証し、検証job自身への依存を作らない。"""
    repo = repo.resolve()
    live_verifier = live_verifier or _default_live_verifier
    head_resolver = head_resolver or _resolve_git_head
    ruleset_reader = ruleset_reader or _default_ruleset_reader
    findings: list[dict[str, str]] = []
    try:
        inspected_head = head_resolver(repo)
    except (OSError, subprocess.SubprocessError, ValueError):
        inspected_head = ""
    if not _is_digest(inspected_head, length=40):
        _finding(findings, "ci_exact_head_unavailable")
        live: dict[str, Any] = {}
    else:
        try:
            live = live_verifier("CI-001", {"inspected_head": inspected_head})
        except (OSError, ValueError, urllib.error.URLError):
            live = {}
            _finding(findings, "ci_live_readback_unavailable")
    if live:
        live_head = live.get("head_sha")
        if not isinstance(live_head, str) or live_head.lower() != inspected_head:
            _finding(findings, "ci_exact_head_mismatch")
        jobs = live.get("jobs")
        if not isinstance(jobs, dict):
            _finding(findings, "ci_jobs_unavailable")
        else:
            for job in REQUIRED_CI_JOBS:
                conclusion = jobs.get(job)
                if conclusion != "success":
                    _finding(
                        findings,
                        "ci_required_job_not_successful",
                        job=job,
                        conclusion=str(conclusion or "pending"),
                    )
    # ruleset整合はCI-001完了条件の実行時SSOT。post-CI verifierはprerequisite jobsのみを
    # 判定し、ruleset書換自体はoperator gate（本エージェントからは403）とする。
    ruleset_contexts: frozenset[str] = frozenset()
    ruleset_read_ok = False
    try:
        ruleset_contexts = ruleset_reader()
        ruleset_read_ok = True
    except (OSError, ValueError, urllib.error.URLError):
        ruleset_read_ok = False
    ruleset_aligned = ruleset_read_ok and set(RULESET_REQUIRED_CHECKS).issubset(
        ruleset_contexts
    )
    valid = not findings
    return {
        "schema": "space_civilization_ci_exact_head_check.v1",
        "contract_valid": valid,
        "state": "exact_head_ci_verified" if valid else "blocked",
        "inspected_head": inspected_head,
        "required_jobs": list(REQUIRED_CI_JOBS),
        "ruleset_required_checks": list(RULESET_REQUIRED_CHECKS),
        "ruleset_id": ACTIVE_MAIN_RULESET_ID,
        "ruleset_live_contexts": sorted(ruleset_contexts),
        "ruleset_aligned": ruleset_aligned,
        "ruleset_read_ok": ruleset_read_ok,
        "findings": findings,
        "external_actions_performed": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="project goal contractを検査する。")
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--static-ci", action="store_true")
    parser.add_argument("--verify-ci-head", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = (
        build_ci_exact_head_report(args.repo)
        if args.verify_ci_head
        else build_report(args.repo, verify_ci_live=not args.static_ci)
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"state: {report['state']}")
        print(f"contract_valid: {str(report['contract_valid']).lower()}")
        if "product_mvp_complete" in report:
            print(f"product_mvp_complete: {str(report['product_mvp_complete']).lower()}")
        for finding in report["findings"]:
            print(f"- {finding}")
    return 0 if report["contract_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
