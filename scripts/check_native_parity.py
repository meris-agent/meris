#!/usr/bin/env python3
"""Run meris-rs ↔ Python parity tests (P5-1). Skips if meris-rs not built."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_native_parity.py", "-q"],
        cwd=ROOT,
        check=False,
    )
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
