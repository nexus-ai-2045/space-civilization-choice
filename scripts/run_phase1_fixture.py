#!/usr/bin/env python3
"""Phase 1 fixtureを実行し、canonical JSONをstdoutへ出す。"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_civilization import load_fixture, run_simulation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", nargs="?", default=ROOT / "fixtures/phase1_domestic_autonomy.json", type=Path)
    parser.add_argument("--output-dir", type=Path, help="manifestとJSONL event logを新規directoryへ保存する")
    args = parser.parse_args()
    result = run_simulation(load_fixture(args.fixture))
    if args.output_dir:
        if args.output_dir.exists():
            raise FileExistsError(f"run output already exists: {args.output_dir}")
        args.output_dir.parent.mkdir(parents=True, exist_ok=True)
        stored_manifest = {
            "schema": "space_civilization_stored_run.v1",
            **result["manifest"],
            "event_count": len(result["events"]),
            "event_log_hash": result["event_log_hash"],
            "canonical_output_hash": result["canonical_output_hash"],
        }
        with tempfile.TemporaryDirectory(prefix=".phase1-run-", dir=args.output_dir.parent) as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "run-manifest.json").write_text(
                json.dumps(stored_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
            )
            (temp_path / "events.jsonl").write_text(
                "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in result["events"]),
                encoding="utf-8",
            )
            (temp_path / "trace.jsonl").write_text(
                "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in result["trace"]),
                encoding="utf-8",
            )
            temp_path.replace(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
