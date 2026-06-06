#!/usr/bin/env python3
"""Compare meris-rs tools schemas with Python ToolRegistry (P5-3)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NATIVE_TOOLS = ("read_file", "glob", "grep", "bash")


def _python_schemas(read_only: bool) -> list[dict]:
    from meris.harness.settings import load_settings
    from meris.tools import build_tools

    reg = build_tools(ROOT, read_only=read_only)
    by_name = {s["function"]["name"]: s for s in reg.schemas()}
    names = ["read_file", "glob", "grep"] if read_only else list(NATIVE_TOOLS)
    return [by_name[n] for n in names if n in by_name]


def _rust_schemas(read_only: bool) -> list[dict] | None:
    from meris.native import find_native_binary

    binary = find_native_binary()
    if not binary:
        return None
    cmd = [str(binary), "tools", "schemas"]
    if read_only:
        cmd.append("--read-only")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    if proc.returncode != 0:
        return None
    data = json.loads(proc.stdout)
    if not isinstance(data, list):
        return None
    return data


def _diff(a: dict, b: dict, label: str) -> list[str]:
    errs: list[str] = []
    if a != b:
        if a.get("function", {}).get("name") != b.get("function", {}).get("name"):
            errs.append(f"{label}: name mismatch")
        elif a.get("function", {}).get("parameters") != b.get("function", {}).get("parameters"):
            errs.append(f"{label}: parameters mismatch")
        elif a.get("function", {}).get("description") != b.get("function", {}).get("description"):
            errs.append(f"{label}: description mismatch")
        else:
            errs.append(f"{label}: schema mismatch")
    return errs


def main() -> int:
    from meris.native import find_native_binary

    if find_native_binary() is None:
        print("skip: meris-rs not built")
        return 0

    errors: list[str] = []
    for read_only in (True, False):
        py = _python_schemas(read_only)
        rs = _rust_schemas(read_only)
        if rs is None:
            print("fail: meris-rs tools schemas unavailable (rebuild meris-rs)")
            return 1
        if len(py) != len(rs):
            errors.append(f"read_only={read_only}: count py={len(py)} rs={len(rs)}")
            continue
        for p, r in zip(py, rs):
            name = p["function"]["name"]
            errors.extend(_diff(p, r, name))

    if errors:
        for e in errors:
            print(e)
        return 1
    print("tool schemas parity OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
