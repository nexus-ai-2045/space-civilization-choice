from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_operational_adoption", ROOT / "scripts" / "check_operational_adoption.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OperationalAdoptionTest(unittest.TestCase):
    def test_repository_contract_is_valid(self) -> None:
        report = MODULE.build_report(ROOT)
        self.assertTrue(report["contract_valid"], report["findings"])
        self.assertEqual(report["counts"]["enforced_ci"], 1)
        self.assertEqual(report["counts"]["operator_gate"], 3)

    def test_private_source_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            shutil.copytree(ROOT / "ops", repo / "ops")
            shutil.copytree(ROOT / ".github", repo / ".github")
            shutil.copytree(ROOT / ".ai-ratchet-gate", repo / ".ai-ratchet-gate")
            for relative in (
                "PROJECT_GOAL.md",
                "PROJECT_SSOT.md",
                "PREFLIGHT.md",
                "PUBLIC_READY.md",
            ):
                shutil.copy2(ROOT / relative, repo / relative)
            shutil.copytree(ROOT / "docs", repo / "docs")
            manifest_path = repo / "ops" / "adoption-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            internal = next(
                entry
                for entry in manifest["entries"]
                if entry["source_visibility"] == "private_internal"
            )
            internal["repository_url"] = "https://github.com/example/private"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = MODULE.build_report(repo)
            self.assertIn(
                "private_source_identity_exposed",
                {finding["code"] for finding in report["findings"]},
            )

    def test_future_candidate_cannot_claim_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            shutil.copytree(ROOT, repo, dirs_exist_ok=True)
            manifest_path = repo / "ops" / "adoption-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            candidate = next(
                entry
                for entry in manifest["entries"]
                if entry["adoption_level"] == "future_candidate"
            )
            candidate["evidence_paths"] = ["README.md"]
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = MODULE.build_report(repo)
            self.assertIn(
                "non_adopted_has_evidence_paths",
                {finding["code"] for finding in report["findings"]},
            )


if __name__ == "__main__":
    unittest.main()
