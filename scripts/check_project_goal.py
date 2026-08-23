#!/usr/bin/env python3
"""Project goal contract の構造、文書間整合、状態遷移を検査する。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "PROJECT_GOAL.md",
    "README.md",
    "docs/PRODUCT_SPEC.md",
    "docs/ROADMAP.md",
    "docs/SIMULATION_DESIGN.md",
    "docs/RESEARCH_EVIDENCE.md",
    "docs/adr/0005-adaptive-exploratory-decision-loop.md",
    "docs/adr/README.md",
)

GOAL_ID = "space-civilization-choice-mvp-v1"
OWNER = "repository-maintainers"
GOAL_STATUSES = {"design", "active", "complete"}

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

REQUIRED_LINKS = {
    "README.md": ("PROJECT_GOAL.md",),
    "docs/ROADMAP.md": ("../PROJECT_GOAL.md",),
    "docs/adr/README.md": ("0005-adaptive-exploratory-decision-loop.md",),
}

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
CHECKBOX_RE = re.compile(
    r"^- \[(?P<checked>[ xX])\] `(?P<id>[A-Z]+-\d{3})`: (?P<body>.+)$",
    re.MULTILINE,
)
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\((?P<target>[^)]+)\)")
FENCE_RE = re.compile(r"^(```|~~~).*?^\1\s*$", re.MULTILINE | re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _read(repo: Path, relative: str) -> str:
    return (repo / relative).read_text(encoding="utf-8")


def _content(text: str) -> str:
    """front matter、code fence、HTML commentを構造検査の対象外にする。"""
    text = FRONT_MATTER_RE.sub("", text, count=1)
    text = FENCE_RE.sub("", text)
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
        values[key.strip()] = value.strip().strip('"\'')
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


def build_report(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    findings: list[dict[str, str]] = []

    for relative in REQUIRED_FILES:
        if not (repo / relative).is_file():
            _finding(findings, "missing_file", path=relative)

    documents = {
        relative: _read(repo, relative)
        for relative in REQUIRED_FILES
        if (repo / relative).is_file()
    }
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
    for goal_id in sorted(checked_ids):
        body = by_id[goal_id][0].group("body")
        evidence_links = _markdown_links(body)
        if not evidence_links:
            _finding(findings, "checked_without_evidence", value=goal_id)
            continue
        for target in evidence_links:
            resolved = _resolved_link(repo, "PROJECT_GOAL.md", target)
            if resolved is None or not resolved.is_file():
                _finding(
                    findings,
                    "invalid_done_when_evidence",
                    value=goal_id,
                    target=target,
                )

    all_complete = len(checked_ids) == len(DONE_WHEN_IDS)
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

    adr = documents.get(
        "docs/adr/0005-adaptive-exploratory-decision-loop.md", ""
    )
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
                field=key,
                expected=expected,
                actual=actual or "",
            )
    adr_headings = set(HEADING_RE.findall(_content(adr)))
    for heading in (
        "Context",
        "Decision",
        "Consequences",
        "Review Evidence",
        "Next Actions",
    ):
        if heading not in adr_headings:
            _finding(findings, "adr_heading_missing", value=heading)

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
        "schema": "space_civilization_project_goal_check.v2",
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
