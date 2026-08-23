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

        self.assertEqual(report["schema"], "space_civilization_project_goal_check.v3")
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
                "| `provenance_type` | `official_source` / `human_input` / "
                "`deterministic_core` / `llm` | どこから来たか |"
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
