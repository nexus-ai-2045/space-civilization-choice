#!/usr/bin/env python3
"""run bundleの生成または再検証を行う。"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_civilization.run_bundle import (  # noqa: E402
    build_run_bundle,
    canonical_bundle_json,
    load_strict_json,
    verify_run_bundle,
)


def _atomic_write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    if (args.output is None) == (args.verify is None):
        parser.error("outputまたは--verifyのどちらか一方を指定してください")
    if args.verify is not None:
        payload = load_strict_json(args.verify)
        verify_run_bundle(payload, ROOT)
        print("run bundle: verified")
        return 0
    bundle = build_run_bundle(ROOT)
    _atomic_write_new(args.output, canonical_bundle_json(bundle))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
