"""`python -m meris` entrypoint."""

from __future__ import annotations

import subprocess
import sys


def test_python_m_meris_harness_check() -> None:
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "meris", "harness", "check", "--cwd", str(root)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
