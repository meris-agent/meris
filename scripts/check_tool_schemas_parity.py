#!/usr/bin/env python3
"""Compare meris-rs tools schemas with Python ToolRegistry (P5-3/ M2)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

READONLY_NATIVE = ("read_file", "glob", "grep")
RUN_NATIVE = ("read_file", "glob", "grep", "write_file", "edit_file", "bash")


def _python_schemas(read_only: bool) -> dict[str, dict]:
    from meris.tools import build_tools

    reg = build_tools(ROOT, read_only=read_only)
    return {s["function"]["name"]: s for s in reg.schemas()}


def _rust_schemas(read_only: bool) -> dict[str, dict] | None:
    from meris.native import find_native_binary

    binary = find_native_binary()
    if not binary:
        return None
    cmd = [str(binary), "tools", "schemas"]
    if read_only:
        cmd.append("--read-only")
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, check=False
    )
    if proc.returncode != 0:
        return None
    data = json.loads(proc.stdout)
    if not isinstance(data, list):
        return None
    return {s["function"]["name"]: s for s in data}


def _diff(a: dict, b: dict, label: str) -> list[str]:
    errs: list[str] = []
    if a.get("function", {}).get("parameters") != b.get("function", {}).get("parameters"):
        errs.append(f"{label}: parameters mismatch")
    return errs


def main() -> int:
    from meris.native import find_native_binary

    if find_native_binary() is None:
        print("skip: meris-rs not built")
        return 0

    errors: list[str] = []
    for read_only in (True, False):
        names = READONLY_NATIVE if read_only else RUN_NATIVE
        py = _python_schemas(read_only)
        rs = _rust_schemas(read_only)
        if rs is None:
            print("fail: meris-rs tools schemas unavailable (rebuild meris-rs)")
            return 1
        for name in names:
            if name not in py:
                errors.append(f"python missing {name}")
                continue
            if name not in rs:
                errors.append(f"rust missing {name}")
                continue
            errors.extend(_diff(py[name], rs[name], name))

    if errors:
        for e in errors:
            print(e)
        return 1
    print("tool schemas parity OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
