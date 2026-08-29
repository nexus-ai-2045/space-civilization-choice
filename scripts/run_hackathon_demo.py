#!/usr/bin/env python3
"""ハッカソン用ローカルWebデモを起動する。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_civilization.web_demo import serve  # noqa: E402


if __name__ == "__main__":
    serve()
