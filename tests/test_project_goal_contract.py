from __future__ import annotations

import importlib.util
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
    def _copy_contract(self, destination: Path) -> None:
        for relative in MODULE.REQUIRED_FILES:
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            source = ROOT / relative
            path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    def _mutated_report(self, relative: str, old: str, new: str):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            path = tmp_path / relative
            original = path.read_text(encoding="utf-8")
            self.assertIn(old, original)
            path.write_text(original.replace(old, new, 1), encoding="utf-8")
            return MODULE.build_report(tmp_path)

    def test_repository_goal_contract_is_valid_but_product_is_incomplete(self) -> None:
        report = MODULE.build_report(ROOT)

        self.assertTrue(report["contract_valid"], report["findings"])
        self.assertEqual(report["state"], "contract_valid_product_incomplete")
        self.assertEqual(report["goal_status"], "design")
        self.assertFalse(report["product_mvp_complete"])
        self.assertEqual(report["checked_done_when_ids"], [])
        self.assertFalse(report["external_actions_performed"])

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
            text = text.replace(
                "- [ ] `GOAL-001`: 本文書、README、プロダクト仕様のゴール・非目標・ownerが矛盾しない",
                "- [x] `GOAL-001`: 本文書、README、プロダクト仕様のゴール・非目標・ownerが矛盾しない。証拠: [README](README.md)",
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

            self.assertTrue(report["contract_valid"], report["findings"])
            self.assertEqual(report["goal_status"], "active")
            self.assertEqual(report["checked_done_when_ids"], ["GOAL-001"])
            self.assertFalse(report["product_mvp_complete"])

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
        self.assertIn("missing_contract_link", {item["code"] for item in report["findings"]})

    def test_broken_contract_link_is_rejected(self) -> None:
        report = self._mutated_report(
            "docs/ROADMAP.md",
            "[`PROJECT_GOAL.md`](../PROJECT_GOAL.md)",
            "[`PROJECT_GOAL.md`](../PROJECT_GOAL.md.broken)",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn("missing_contract_link", {item["code"] for item in report["findings"]})

    def test_product_owner_drift_is_rejected(self) -> None:
        report = self._mutated_report(
            "docs/PRODUCT_SPEC.md",
            "owner: repository-maintainers",
            "owner: nobody",
        )

        self.assertFalse(report["contract_valid"])
        self.assertIn("product_metadata_mismatch", {item["code"] for item in report["findings"]})

    def test_empty_adr_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            self._copy_contract(tmp_path)
            (tmp_path / "docs/adr/0005-adaptive-exploratory-decision-loop.md").write_text(
                "", encoding="utf-8"
            )

            report = MODULE.build_report(tmp_path)

            self.assertFalse(report["contract_valid"])
            self.assertIn("adr_metadata_mismatch", {item["code"] for item in report["findings"]})


if __name__ == "__main__":
    unittest.main()
