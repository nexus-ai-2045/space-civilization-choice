from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_project_goal.py"
SPEC = importlib.util.spec_from_file_location("check_project_goal", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProjectGoalContractTest(unittest.TestCase):
    def test_artifact_hash_bytes_are_os_independent_for_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_bytes(b'{"ok": true}\r\n')

            self.assertEqual(
                MODULE._canonical_artifact_bytes(path),
                b'{"ok": true}\n',
            )

    def _copy_contract(self, destination: Path) -> None:
        for relative in MODULE.REQUIRED_FILES:
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            source = ROOT / relative
            content = source.read_text(encoding="utf-8")
            # Mutation tests begin from the original all-unchecked design state.
            # The repository itself may legitimately advance to active as receipts land.
            if relative == "PROJECT_GOAL.md":
                content = content.replace("status: active", "status: design", 1)
                content = content.replace("- `status`: active", "- `status`: design", 1)
                content = content.replace(
                    "- [x] `REPLAY-001`: [receipt](evidence/done-when/REPLAY-001.json) ",
                    "- [ ] `REPLAY-001`: ",
                    1,
                )
                content = content.replace(
                    "- [x] `TRACE-001`: [receipt](evidence/done-when/TRACE-001.json) ",
                    "- [ ] `TRACE-001`: ",
                    1,
                )
                content = content.replace(
                    "- [x] `CI-001`: [receipt](evidence/done-when/CI-001.json) ",
                    "- [ ] `CI-001`: ",
                    1,
                )
            elif relative == "docs/PRODUCT_SPEC.md":
                content = content.replace("status: active", "status: design", 1)
            path.write_text(content, encoding="utf-8")

    def _mutated_report(self, relative: str, old: str, new: str):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            path = tmp_path / relative
            original = path.read_text(encoding="utf-8")
            self.assertIn(old, original)
            path.write_text(original.replace(old, new, 1), encoding="utf-8")
            return MODULE.build_report(tmp_path)

    def _write_goal_evidence(self, repo: Path) -> None:
        self._write_evidence_receipt(
            repo,
            "GOAL-001",
            {
                "goal_contract": "PROJECT_GOAL.md",
                "readme": "README.md",
                "product_spec": "docs/PRODUCT_SPEC.md",
            },
            result={
                "consistent": True,
                "documents": [
                    "PROJECT_GOAL.md",
                    "README.md",
                    "docs/PRODUCT_SPEC.md",
                ],
            },
        )

    def _write_evidence_receipt(
        self,
        repo: Path,
        goal_id: str,
        artifacts: dict[str, str],
        result=None,
    ) -> None:
        path = repo / "evidence" / "done-when" / f"{goal_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": MODULE.DONE_WHEN_EVIDENCE_SCHEMA,
            "done_when_id": goal_id,
            "evidence_type": MODULE.DONE_WHEN_EVIDENCE_CONTRACTS[goal_id][
                "evidence_type"
            ],
            "status": "passed",
            "artifacts": artifacts,
            "artifact_sha256": {
                role: hashlib.sha256(
                    MODULE._canonical_artifact_bytes(repo / target)
                ).hexdigest()
                for role, target in artifacts.items()
            },
        }
        if result is not None:
            payload["result"] = result
        path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    def _activate_done_when(self, repo: Path, goal_id: str) -> None:
        goal = repo / "PROJECT_GOAL.md"
        text = goal.read_text(encoding="utf-8")
        text = text.replace("status: design", "status: active", 1)
        text = text.replace("- `status`: design", "- `status`: active", 1)
        text = text.replace(
            f"- [ ] `{goal_id}`:",
            f"- [x] `{goal_id}`: [receipt](evidence/done-when/{goal_id}.json) ",
            1,
        )
        goal.write_text(text, encoding="utf-8")
        product = repo / "docs" / "PRODUCT_SPEC.md"
        product.write_text(
            product.read_text(encoding="utf-8").replace(
                "status: design", "status: active", 1
            ),
            encoding="utf-8",
        )

    def _write_branch_evidence(self, repo: Path, *, legacy_field: bool = False) -> None:
        test_path = repo / "tests" / "branch_evidence.py"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(
            (
                "def test_branch_contract():\n"
                "    branch = scenario_snapshot_hash = exogenous_event_stream_hash = True\n"
                "    event_log_hash = True\n"
                "    assert branch and scenario_snapshot_hash and "
                "exogenous_event_stream_hash and event_log_hash\n"
            ),
            encoding="utf-8",
        )
        stream_field = (
            "event_stream_hash" if legacy_field else "exogenous_event_stream_hash"
        )
        manifest_path = repo / "evidence" / "runs" / "branches.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "space_civilization_run_manifest.v1",
                    "branches": [
                        {
                            "branch_id": f"branch-{index}",
                            "scenario_snapshot_hash": "a" * 64,
                            "seed": 7,
                            "model_version": "v1",
                            stream_field: "b" * 64,
                            "event_log_hash": character * 64,
                        }
                        for index, character in enumerate("cde", start=1)
                    ],
                }
            ),
            encoding="utf-8",
        )
        self._write_evidence_receipt(
            repo,
            "BRANCH-001",
            {
                "test": "tests/branch_evidence.py",
                "run_manifest": "evidence/runs/branches.json",
            },
        )

    def _write_ci_evidence(self, repo: Path, head_sha: str) -> str:
        workflow = repo / ".github" / "workflows" / "completion.yml"
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text(
            "jobs:\n"
            + "\n".join(f"  # {job}" for job in MODULE.REQUIRED_CI_JOBS),
            encoding="utf-8",
        )
        ci_receipt = repo / "evidence" / "ci" / "ci.json"
        ci_receipt.parent.mkdir(parents=True, exist_ok=True)
        run_url = f"{MODULE.CANONICAL_REPOSITORY_URL}/actions/runs/123"
        ci_receipt.write_text(
            json.dumps(
                {
                    "schema": "space_civilization_ci_receipt.v1",
                    "repository": MODULE.CANONICAL_REPOSITORY,
                    "head_sha": head_sha,
                    "conclusion": "success",
                    "jobs": {job: "success" for job in MODULE.REQUIRED_CI_JOBS},
                    "run_url": run_url,
                }
            ),
            encoding="utf-8",
        )
        self._write_evidence_receipt(
            repo,
            "CI-001",
            {
                "workflow": ".github/workflows/completion.yml",
                "ci_receipt": "evidence/ci/ci.json",
            },
        )
        return run_url

    def _write_human_evidence(self, repo: Path) -> None:
        review = repo / "evidence" / "reviews" / "review.json"
        review.parent.mkdir(parents=True, exist_ok=True)
        review.write_text(
            json.dumps(
                {
                    "schema": "space_civilization_human_review.v1",
                    "duration_minutes": 20,
                    "reviewer_count": 1,
                    "comparison_completed": True,
                    "model_causality_explained": True,
                    "review_findings": ["model causality understood"],
                    "reviewed_at": "2026-08-24T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )
        self._write_evidence_receipt(
            repo,
            "HUMAN-001",
            {"review_record": "evidence/reviews/review.json"},
        )

    def _write_public_evidence(self, repo: Path, head_sha: str) -> None:
        checklist = repo / "PUBLIC_READY.md"
        checklist.write_text(
            checklist.read_text(encoding="utf-8").replace("- [ ]", "- [x]"),
            encoding="utf-8",
        )
        readback = repo / "evidence" / "publication" / "readback.json"
        readback.parent.mkdir(parents=True, exist_ok=True)
        readback.write_text(
            json.dumps(
                {
                    "schema": "space_civilization_public_readback.v1",
                    "repository": MODULE.CANONICAL_REPOSITORY,
                    "visibility": "public",
                    "default_branch": "main",
                    "head_sha": head_sha,
                    "readback_url": MODULE.CANONICAL_REPOSITORY_URL,
                    "human_reviewed": True,
                    "secret_scan_clear": True,
                    "personal_path_scan_clear": True,
                }
            ),
            encoding="utf-8",
        )
        self._write_evidence_receipt(
            repo,
            "PUBLIC-001",
            {
                "checklist": "PUBLIC_READY.md",
                "readback": "evidence/publication/readback.json",
            },
        )

    def test_repository_goal_contract_is_active_but_product_is_incomplete(self) -> None:
        ci_receipt = json.loads(
            (ROOT / "evidence/ci/phase1-exact-head-ecde21d.json").read_text(encoding="utf-8")
        )

        def live_verifier(goal_id, evidence):
            if goal_id != "CI-001":
                raise AssertionError(f"unexpected live readback for {goal_id}")
            self.assertEqual(evidence.get("head_sha"), ci_receipt["head_sha"])
            return {
                "repository": MODULE.CANONICAL_REPOSITORY,
                "head_sha": ci_receipt["head_sha"],
                "conclusion": "success",
                "run_url": ci_receipt["run_url"],
                "jobs": {job: "success" for job in MODULE.REQUIRED_CI_JOBS},
            }

        report = MODULE.build_report(ROOT, live_verifier=live_verifier)

        self.assertEqual(report["schema"], "space_civilization_project_goal_check.v3")
        self.assertTrue(report["contract_valid"], report["findings"])
        self.assertEqual(report["state"], "contract_valid_product_incomplete")
        self.assertEqual(report["goal_status"], "active")
        self.assertFalse(report["product_mvp_complete"])
        self.assertEqual(
            report["checked_done_when_ids"],
            ["CI-001", "REPLAY-001", "TRACE-001"],
        )
        self.assertFalse(report["external_actions_performed"])

    def test_replay_rejects_stored_hash_decoupled_from_replay_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            for relative in (
                "tests/test_phase1_simulation.py",
                "evidence/runs/phase1-replay.json",
                "evidence/runs/phase1-domestic-autonomy-20260828-v2/run-manifest.json",
                "evidence/runs/phase1-domestic-autonomy-20260828-v2/events.jsonl",
                "evidence/done-when/REPLAY-001.json",
            ):
                source = ROOT / relative
                target = tmp_path / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())

            goal = tmp_path / "PROJECT_GOAL.md"
            text = goal.read_text(encoding="utf-8")
            text = text.replace("status: design", "status: active", 1)
            text = text.replace("- `status`: design", "- `status`: active", 1)
            text = text.replace(
                "- [ ] `REPLAY-001`:",
                "- [x] `REPLAY-001`: [receipt](evidence/done-when/REPLAY-001.json) ",
                1,
            )
            goal.write_text(text, encoding="utf-8")
            product = tmp_path / "docs" / "PRODUCT_SPEC.md"
            product.write_text(
                product.read_text(encoding="utf-8").replace(
                    "status: design", "status: active", 1
                ),
                encoding="utf-8",
            )

            stored = tmp_path / "evidence/runs/phase1-domestic-autonomy-20260828-v2/run-manifest.json"
            payload = json.loads(stored.read_text(encoding="utf-8"))
            payload["canonical_output_hash"] = "b" * 64
            stored.write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            receipt = tmp_path / "evidence/done-when/REPLAY-001.json"
            receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
            receipt_payload["artifact_sha256"]["canonical_manifest"] = hashlib.sha256(
                stored.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            receipt.write_text(json.dumps(receipt_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            report = MODULE.build_report(tmp_path)

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "invalid_done_when_evidence",
            {item["code"] for item in report["findings"]},
        )

    def test_missing_done_when_blocks_contract(self) -> None:
        report = self._mutated_report(
            "PROJECT_GOAL.md",
            "- [ ] `TRACE-001`:",
            "- [ ] `REMOVED-001`:",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn("TRACE-001", {item.get("value") for item in report["findings"]})

    def test_checked_done_when_with_evidence_can_enter_active_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            goal = tmp_path / "PROJECT_GOAL.md"
            text = goal.read_text(encoding="utf-8")
            text = text.replace("status: design", "status: active", 1)
            text = text.replace("- `status`: design", "- `status`: active", 1)
            text = text.replace(
                "- [ ] `GOAL-001`: 本文書、README、プロダクト仕様のゴール・非目標・ownerが矛盾しない",
                "- [x] `GOAL-001`: 本文書、README、プロダクト仕様のゴール・非目標・ownerが矛盾しない。証拠: [receipt](evidence/done-when/GOAL-001.json)",
                1,
            )
            goal.write_text(text, encoding="utf-8")
            product = tmp_path / "docs" / "PRODUCT_SPEC.md"
            product.write_text(
                product.read_text(encoding="utf-8").replace(
                    "status: design", "status: active", 1
                ),
                encoding="utf-8",
            )
            self._write_goal_evidence(tmp_path)

            report = MODULE.build_report(tmp_path)

            self.assertTrue(report["contract_valid"], report["findings"])
            self.assertEqual(report["goal_status"], "active")
            self.assertEqual(report["checked_done_when_ids"], ["GOAL-001"])
            self.assertFalse(report["product_mvp_complete"])

    def test_checked_done_when_rejects_unrelated_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            goal = tmp_path / "PROJECT_GOAL.md"
            text = goal.read_text(encoding="utf-8")
            text = text.replace("status: design", "status: active", 1)
            text = text.replace("- `status`: design", "- `status`: active", 1)
            text = text.replace(
                "- [ ] `REPLAY-001`:",
                "- [x] `REPLAY-001`: [unrelated](README.md) ",
                1,
            )
            goal.write_text(text, encoding="utf-8")
            product = tmp_path / "docs" / "PRODUCT_SPEC.md"
            product.write_text(
                product.read_text(encoding="utf-8").replace(
                    "status: design", "status: active", 1
                ),
                encoding="utf-8",
            )
            report = MODULE.build_report(tmp_path)

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "invalid_done_when_evidence",
            {item["code"] for item in report["findings"]},
        )

    def test_unterminated_fenced_block_is_rejected(self) -> None:
        report = self._mutated_report(
            "PROJECT_GOAL.md",
            "# プロジェクトゴール",
            "```text\n# プロジェクトゴール",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "unterminated_code_fence",
            {item["code"] for item in report["findings"]},
        )

    def test_html_comment_literal_inside_fence_does_not_hide_closer(self) -> None:
        report = self._mutated_report(
            "PROJECT_GOAL.md",
            "# プロジェクトゴール",
            "```text\n<!-- literal comment opener\n```\n# プロジェクトゴール",
        )

        self.assertTrue(report["contract_valid"], report["findings"])

    def test_unterminated_html_comment_outside_fence_is_rejected(self) -> None:
        report = self._mutated_report(
            "PROJECT_GOAL.md",
            "# プロジェクトゴール",
            "<!-- open comment\n# プロジェクトゴール",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "unterminated_html_comment",
            {item["code"] for item in report["findings"]},
        )

    def test_same_line_closed_comment_followed_by_open_comment_is_rejected(self) -> None:
        report = self._mutated_report(
            "PROJECT_GOAL.md",
            "# プロジェクトゴール",
            "<!-- closed --> <!-- reopened\n# プロジェクトゴール",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "unterminated_html_comment",
            {item["code"] for item in report["findings"]},
        )

    def test_branch_uses_exogenous_stream_and_distinct_event_logs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            self._activate_done_when(tmp_path, "BRANCH-001")
            self._write_branch_evidence(tmp_path)

            report = MODULE.build_report(tmp_path)

        self.assertTrue(report["contract_valid"], report["findings"])

    def test_branch_rejects_legacy_event_stream_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            self._activate_done_when(tmp_path, "BRANCH-001")
            self._write_branch_evidence(tmp_path, legacy_field=True)

            report = MODULE.build_report(tmp_path)

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "invalid_done_when_evidence",
            {item["code"] for item in report["findings"]},
        )

    def test_ci_self_certification_requires_matching_live_readback(self) -> None:
        inspected_head = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            self._activate_done_when(tmp_path, "CI-001")
            workflow = tmp_path / ".github" / "workflows" / "completion.yml"
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(
                "jobs:\n"
                + "\n".join(f"  # {job}" for job in MODULE.REQUIRED_CI_JOBS),
                encoding="utf-8",
            )
            ci_receipt = tmp_path / "evidence" / "ci" / "ci.json"
            ci_receipt.parent.mkdir(parents=True, exist_ok=True)
            run_url = f"{MODULE.CANONICAL_REPOSITORY_URL}/actions/runs/123"
            ci_receipt.write_text(
                json.dumps(
                    {
                        "schema": "space_civilization_ci_receipt.v1",
                        "repository": MODULE.CANONICAL_REPOSITORY,
                        "head_sha": inspected_head,
                        "conclusion": "success",
                        "jobs": {job: "success" for job in MODULE.REQUIRED_CI_JOBS},
                        "run_url": run_url,
                    }
                ),
                encoding="utf-8",
            )
            self._write_evidence_receipt(
                tmp_path,
                "CI-001",
                {
                    "workflow": ".github/workflows/completion.yml",
                    "ci_receipt": "evidence/ci/ci.json",
                },
            )

            report = MODULE.build_report(
                tmp_path,
                head_resolver=lambda _: inspected_head,
                live_verifier=lambda _goal_id, _evidence: {
                    "repository": MODULE.CANONICAL_REPOSITORY,
                    "head_sha": "b" * 40,
                    "conclusion": "success",
                    "run_url": run_url,
                    "jobs": {job: "success" for job in MODULE.REQUIRED_CI_JOBS},
                },
            )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "ci_live_readback_mismatch",
            {item.get("reason") for item in report["findings"]},
        )

    def test_ci_receipt_may_bind_to_ancestor_exact_head(self) -> None:
        ancestor = "a" * 40
        tip = "b" * 40
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            self._activate_done_when(tmp_path, "CI-001")
            run_url = self._write_ci_evidence(tmp_path, ancestor)

            report = MODULE.build_report(
                tmp_path,
                head_resolver=lambda _: tip,
                live_verifier=lambda _goal_id, _evidence: {
                    "repository": MODULE.CANONICAL_REPOSITORY,
                    "head_sha": ancestor,
                    "conclusion": "success",
                    "run_url": run_url,
                    "jobs": {job: "success" for job in MODULE.REQUIRED_CI_JOBS},
                },
            )
            # TemporaryDirectory is not a git repo; ancestor check fails closed.
            self.assertFalse(report["contract_valid"])

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            self._activate_done_when(tmp_path, "CI-001")
            run_url = self._write_ci_evidence(tmp_path, tip)

            report = MODULE.build_report(
                tmp_path,
                head_resolver=lambda _: tip,
                live_verifier=lambda _goal_id, _evidence: {
                    "repository": MODULE.CANONICAL_REPOSITORY,
                    "head_sha": tip,
                    "conclusion": "success",
                    "run_url": run_url,
                    "jobs": {job: "success" for job in MODULE.REQUIRED_CI_JOBS},
                },
            )

        self.assertTrue(report["contract_valid"], report["findings"])
        self.assertIn("CI-001", report["checked_done_when_ids"])

    def test_public_requires_validated_ci_and_human_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            self._activate_done_when(tmp_path, "PUBLIC-001")

            report = MODULE.build_report(
                tmp_path,
                live_verifier=lambda *_: (_ for _ in ()).throw(
                    AssertionError("PUBLIC dependencies must fail before network")
                ),
            )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "public_dependency_unvalidated",
            {item.get("reason") for item in report["findings"]},
        )

    def test_public_self_certification_requires_main_live_readback(self) -> None:
        inspected_head = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            self._activate_done_when(tmp_path, "CI-001")
            self._activate_done_when(tmp_path, "HUMAN-001")
            self._activate_done_when(tmp_path, "PUBLIC-001")
            run_url = self._write_ci_evidence(tmp_path, inspected_head)
            self._write_human_evidence(tmp_path)
            self._write_public_evidence(tmp_path, inspected_head)

            def live_verifier(goal_id, _evidence):
                if goal_id == "CI-001":
                    return {
                        "repository": MODULE.CANONICAL_REPOSITORY,
                        "head_sha": inspected_head,
                        "conclusion": "success",
                        "run_url": run_url,
                        "jobs": {
                            job: "success" for job in MODULE.REQUIRED_CI_JOBS
                        },
                    }
                return {
                    "repository": MODULE.CANONICAL_REPOSITORY,
                    "visibility": "public",
                    "default_branch": "main",
                    "main_head": "b" * 40,
                    "repository_url": MODULE.CANONICAL_REPOSITORY_URL,
                    "files": {
                        "README.md": True,
                        "LICENSE": True,
                        "SECURITY.md": True,
                    },
                }

            report = MODULE.build_report(
                tmp_path,
                head_resolver=lambda _: inspected_head,
                live_verifier=live_verifier,
                personal_path_scanner=lambda _: (True, []),
            )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "public_live_readback_mismatch",
            {item.get("reason") for item in report["findings"]},
        )

    def test_public_rejects_missing_local_license_or_security(self) -> None:
        inspected_head = "a" * 40
        for missing in ("LICENSE", "SECURITY.md"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                tmp_path = Path(directory)
                self._copy_contract(tmp_path)
                for goal_id in ("CI-001", "HUMAN-001", "PUBLIC-001"):
                    self._activate_done_when(tmp_path, goal_id)
                run_url = self._write_ci_evidence(tmp_path, inspected_head)
                self._write_human_evidence(tmp_path)
                self._write_public_evidence(tmp_path, inspected_head)
                (tmp_path / missing).unlink()

                report = MODULE.build_report(
                    tmp_path,
                    head_resolver=lambda _: inspected_head,
                    personal_path_scanner=lambda _: (True, []),
                    live_verifier=lambda goal_id, _evidence: {
                        "repository": MODULE.CANONICAL_REPOSITORY,
                        "head_sha": inspected_head,
                        "conclusion": "success",
                        "run_url": run_url,
                        "jobs": {
                            job: "success" for job in MODULE.REQUIRED_CI_JOBS
                        },
                    }
                    if goal_id == "CI-001"
                    else {},
                )

                self.assertFalse(report["contract_valid"])
                self.assertIn(
                    missing,
                    {item.get("path") for item in report["findings"]},
                )

    def test_tracked_personal_path_scan_is_computed_from_repository_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            evidence = repo / "evidence.md"
            windows_path = "C:" + "\\Users\\alice\\secret.txt"
            mac_path = "/" + "Users/alice/private.txt"
            linux_path = "/" + "home/alice/private.txt"
            evidence.write_text(
                f"windows: {windows_path}\n"
                f"mac: {mac_path}\n"
                f"linux: {linux_path}\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(repo), "add", "evidence.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-q",
                    "-m",
                    "fixture",
                ],
                check=True,
            )

            clear, matches = MODULE._scan_tracked_personal_paths(repo)

        self.assertFalse(clear)
        self.assertEqual(matches, ["evidence.md"])

    def test_empty_or_untyped_artifacts_fail_for_every_done_when(self) -> None:
        cases = {
            "GOAL-001": {
                "goal_contract": "PROJECT_GOAL.md",
                "readme": "README.md",
                "product_spec": "docs/PRODUCT_SPEC.md",
            },
            "REPLAY-001": {
                "test": "tests/replay_evidence.py",
                "run_manifest": "evidence/runs/replay.json",
            },
            "BRANCH-001": {
                "test": "tests/branch_evidence.py",
                "run_manifest": "evidence/runs/branches.json",
            },
            "TRACE-001": {
                "test": "tests/trace_evidence.py",
                "trace": "evidence/runs/trace.json",
            },
            "CLASS-001": {
                "test": "tests/class_evidence.py",
                "validation_report": "evidence/reports/class.json",
            },
            "MODEL-001": {
                "test": "tests/model_evidence.py",
                "model_card": "docs/model-cards/model.md",
            },
            "ROBUST-001": {
                "test": "tests/robust_evidence.py",
                "robustness_report": "evidence/reports/robust.json",
            },
            "FEEDBACK-001": {
                "feedback_record": "evidence/feedback/feedback.json",
            },
            "HUMAN-001": {
                "review_record": "evidence/reviews/review.json",
            },
            "CI-001": {
                "workflow": ".github/workflows/completion.yml",
                "ci_receipt": "evidence/ci/ci.json",
            },
            "PUBLIC-001": {
                "checklist": "PUBLIC_READY.md",
                "readback": "evidence/publication/readback.json",
            },
        }
        for goal_id, artifacts in cases.items():
            with self.subTest(goal_id=goal_id), tempfile.TemporaryDirectory() as directory:
                tmp_path = Path(directory)
                self._copy_contract(tmp_path)
                goal = tmp_path / "PROJECT_GOAL.md"
                text = goal.read_text(encoding="utf-8")
                text = text.replace("status: design", "status: active", 1)
                text = text.replace("- `status`: design", "- `status`: active", 1)
                text = text.replace(
                    f"- [ ] `{goal_id}`:",
                    (
                        f"- [x] `{goal_id}`: "
                        f"[receipt](evidence/done-when/{goal_id}.json) "
                    ),
                    1,
                )
                goal.write_text(text, encoding="utf-8")
                product = tmp_path / "docs" / "PRODUCT_SPEC.md"
                product.write_text(
                    product.read_text(encoding="utf-8").replace(
                        "status: design", "status: active", 1
                    ),
                    encoding="utf-8",
                )
                for target in artifacts.values():
                    artifact = tmp_path / target
                    if artifact.exists():
                        continue
                    artifact.parent.mkdir(parents=True, exist_ok=True)
                    artifact.write_text(
                        "{}" if artifact.suffix == ".json" else "",
                        encoding="utf-8",
                    )
                self._write_evidence_receipt(tmp_path, goal_id, artifacts)

                report = MODULE.build_report(tmp_path)

                self.assertFalse(report["contract_valid"])
                self.assertIn(
                    "invalid_done_when_evidence",
                    {item["code"] for item in report["findings"]},
                )

    def test_checked_unknown_done_when_fails_without_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            goal = tmp_path / "PROJECT_GOAL.md"
            goal.write_text(
                goal.read_text(encoding="utf-8").replace(
                    "- [ ] `TRACE-001`:",
                    "- [x] `UNKNOWN-999`: [evidence](README.md) ",
                    1,
                ),
                encoding="utf-8",
            )

            report = MODULE.build_report(tmp_path)

        codes = {item["code"] for item in report["findings"]}
        self.assertFalse(report["contract_valid"])
        self.assertIn("unknown_done_when", codes)
        self.assertIn("invalid_done_when_evidence", codes)

    def test_displayed_status_must_match_front_matter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            for relative in ("PROJECT_GOAL.md", "docs/PRODUCT_SPEC.md"):
                path = tmp_path / relative
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "status: design", "status: active", 1
                    ),
                    encoding="utf-8",
                )

            report = MODULE.build_report(tmp_path)

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "current_status_mismatch",
            {item["code"] for item in report["findings"]},
        )

    def test_checked_done_when_without_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            for relative in ("PROJECT_GOAL.md", "docs/PRODUCT_SPEC.md"):
                path = tmp_path / relative
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "status: design", "status: active", 1
                    ),
                    encoding="utf-8",
                )
            goal = tmp_path / "PROJECT_GOAL.md"
            goal.write_text(
                goal.read_text(encoding="utf-8").replace(
                    "- [ ] `TRACE-001`:", "- [x] `TRACE-001`:", 1
                ),
                encoding="utf-8",
            )

            report = MODULE.build_report(tmp_path)

            self.assertFalse(report["contract_valid"])
            self.assertIn(
                "checked_without_evidence",
                {item["code"] for item in report["findings"]},
            )

    def test_plain_text_is_not_accepted_as_contract_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            readme = tmp_path / "README.md"
            text = readme.read_text(encoding="utf-8")
            self.assertIn("(PROJECT_GOAL.md)", text)
            readme.write_text(
                text.replace("(PROJECT_GOAL.md)", "(PROJECT_GOAL.md.broken)"),
                encoding="utf-8",
            )
            report = MODULE.build_report(tmp_path)

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "missing_contract_link", {item["code"] for item in report["findings"]}
        )

    def test_broken_contract_link_is_rejected(self) -> None:
        report = self._mutated_report(
            "docs/ROADMAP.md",
            "[`PROJECT_GOAL.md`](../PROJECT_GOAL.md)",
            "[`PROJECT_GOAL.md`](../PROJECT_GOAL.md.broken)",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "missing_contract_link", {item["code"] for item in report["findings"]}
        )

    def test_product_owner_drift_is_rejected(self) -> None:
        report = self._mutated_report(
            "docs/PRODUCT_SPEC.md",
            "owner: repository-maintainers",
            "owner: nobody",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "product_metadata_mismatch", {item["code"] for item in report["findings"]}
        )

    def test_project_ssot_repository_drift_is_rejected(self) -> None:
        report = self._mutated_report(
            "PROJECT_SSOT.md",
            "canonical_repository: nexus-ai-2045/space-civilization-choice",
            "canonical_repository: somebody/parallel-copy",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "ssot_metadata_mismatch",
            {item["code"] for item in report["findings"]},
        )

    def test_project_ssot_canonical_link_is_required(self) -> None:
        report = self._mutated_report(
            "PROJECT_SSOT.md",
            "(docs/SIMULATION_DESIGN.md)",
            "(docs/SIMULATION_DESIGN.md.broken)",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "missing_contract_link",
            {item["code"] for item in report["findings"]},
        )

    def test_project_ssot_canonical_targets_cannot_be_swapped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            path = tmp_path / "PROJECT_SSOT.md"
            text = path.read_text(encoding="utf-8")
            text = text.replace("(PROJECT_GOAL.md)", "(__swap__.md)", 1)
            text = text.replace("(docs/ONE_PAGER.md)", "(PROJECT_GOAL.md)", 1)
            text = text.replace("(__swap__.md)", "(docs/ONE_PAGER.md)", 1)
            path.write_text(text, encoding="utf-8")

            report = MODULE.build_report(tmp_path)

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "ssot_target_mismatch",
            {item["code"] for item in report["findings"]},
        )

    def test_project_ssot_duplicate_and_unexpected_rows_are_rejected(self) -> None:
        report = self._mutated_report(
            "PROJECT_SSOT.md",
            "| `product_goal` |",
            (
                "| `product_goal` | duplicate | [goal](PROJECT_GOAL.md) | duplicate |\n"
                "| `unexpected` | extra | [goal](PROJECT_GOAL.md) | extra |\n"
                "| `product_goal` |"
            ),
        )

        codes = {item["code"] for item in report["findings"]}
        self.assertFalse(report["contract_valid"])
        self.assertIn("ssot_row_duplicate", codes)
        self.assertIn("ssot_concern_unexpected", codes)

    def test_project_ssot_noncanonical_row_is_rejected(self) -> None:
        report = self._mutated_report(
            "PROJECT_SSOT.md",
            "| `product_goal` |",
            "| product_goal | malformed | PROJECT_GOAL.md | missing links |\n| `product_goal` |",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "ssot_row_malformed",
            {item["code"] for item in report["findings"]},
        )

    def test_empty_adr_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            (
                tmp_path / "docs/adr/0005-adaptive-exploratory-decision-loop.md"
            ).write_text("", encoding="utf-8")

            report = MODULE.build_report(tmp_path)

            self.assertFalse(report["contract_valid"])
            self.assertIn(
                "adr_metadata_mismatch", {item["code"] for item in report["findings"]}
            )

    def test_epistemic_schema_adr_terms_are_required(self) -> None:
        report = self._mutated_report(
            "docs/adr/0006-separate-epistemic-provenance-validation.md",
            "epistemic-provenance-validation/v1",
            "removed-schema-contract/v1",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "adr_contract_term_missing",
            {item["code"] for item in report["findings"]},
        )

    def test_each_epistemic_schema_row_is_required(self) -> None:
        rows = {
            "record_kind": (
                "| `record_kind` | `source_claim` / `exogenous_event` / "
                "`simulated_transition` / `action_proposal` | 何を記録しているか |"
            ),
            "epistemic_class": (
                "| `epistemic_class` | `fact` / `scenario_hypothesis` / "
                "`model_assumption` / `inference` / `unknown` | 内容をどの知識状態として扱うか |"
            ),
            "provenance_type": (
                "| `provenance_type` | `official_source` / `academic_source` / "
                "`third_party_public_source` / `human_input` / `deterministic_core` / "
                "`llm` | どこから来たか |"
            ),
            "validation_state": (
                "| `validation_state` | `proposed` / `accepted_for_run` / "
                "`rejected` / `superseded` | runへ採用できる状態か |"
            ),
        }
        for field, row in rows.items():
            with self.subTest(field=field):
                report = self._mutated_report(
                    "docs/adr/0006-separate-epistemic-provenance-validation.md",
                    row,
                    f"| `removed_{field}` | `removed` | removed |",
                )
                self.assertFalse(report["contract_valid"])
                self.assertIn(
                    "adr_schema_row_missing",
                    {item["code"] for item in report["findings"]},
                )

    def test_epistemic_schema_values_are_exact(self) -> None:
        report = self._mutated_report(
            "docs/adr/0006-separate-epistemic-provenance-validation.md",
            "`fact` / `scenario_hypothesis` / `model_assumption` / `inference` / `unknown`",
            "`fact` / `unknown`",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "adr_schema_values_mismatch",
            {item["code"] for item in report["findings"]},
        )

    def test_provenance_source_types_are_exact(self) -> None:
        report = self._mutated_report(
            "docs/adr/0006-separate-epistemic-provenance-validation.md",
            (
                "`official_source` / `academic_source` / "
                "`third_party_public_source` / `human_input` / "
                "`deterministic_core` / `llm`"
            ),
            "`official_source` / `human_input` / `deterministic_core` / `llm`",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "adr_schema_values_mismatch",
            {item["code"] for item in report["findings"]},
        )

    def test_epistemic_schema_duplicate_field_is_rejected(self) -> None:
        row = (
            "| `validation_state` | `proposed` / `accepted_for_run` / "
            "`rejected` / `superseded` | runへ採用できる状態か |"
        )
        report = self._mutated_report(
            "docs/adr/0006-separate-epistemic-provenance-validation.md",
            row,
            ("| `validation_state` | `wrong` | 重複した矛盾row |\n" f"{row}"),
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "adr_schema_row_duplicate",
            {item["code"] for item in report["findings"]},
        )

    def test_epistemic_schema_unexpected_field_is_rejected(self) -> None:
        report = self._mutated_report(
            "docs/adr/0006-separate-epistemic-provenance-validation.md",
            "| `record_kind` |",
            "| `new_axis` | `unversioned` | 未規定の第5軸 |\n| `record_kind` |",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "adr_schema_field_unexpected",
            {item["code"] for item in report["findings"]},
        )

    def test_epistemic_schema_noncanonical_rows_are_rejected(self) -> None:
        rows = (
            "| new_axis | unversioned | 未規定の第5軸 |",
            "| validation_state | wrong | backtickなしの矛盾row |",
        )
        for row in rows:
            with self.subTest(row=row):
                report = self._mutated_report(
                    "docs/adr/0006-separate-epistemic-provenance-validation.md",
                    "| `record_kind` |",
                    f"{row}\n| `record_kind` |",
                )

                self.assertFalse(report["contract_valid"])
                self.assertIn(
                    "adr_schema_row_malformed",
                    {item["code"] for item in report["findings"]},
                )

    def test_epistemic_schema_human_review_gate_is_required(self) -> None:
        report = self._mutated_report(
            "docs/adr/0006-separate-epistemic-provenance-validation.md",
            "## Human Review Gate",
            "## Removed Review Gate",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "adr_heading_missing", {item["code"] for item in report["findings"]}
        )

    def test_epistemic_schema_adr_index_link_is_required(self) -> None:
        report = self._mutated_report(
            "docs/adr/README.md",
            "(0006-separate-epistemic-provenance-validation.md)",
            "(0006-separate-epistemic-provenance-validation.md.broken)",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn(
            "missing_contract_link", {item["code"] for item in report["findings"]}
        )


if __name__ == "__main__":
    unittest.main()
