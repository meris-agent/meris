"""Native (meris-rs) parity with Python harness checks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from meris.harness.permissions import check_tool_allowed
from meris.harness.sandbox import check_bash_sandbox, scan_bash_command
from meris.native import find_native_binary, native_check_tool_allowed


def _meris_rs(*args: str) -> subprocess.CompletedProcess[str] | None:
    binary = find_native_binary()
    if not binary:
        return None
    return subprocess.run(
        [str(binary), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )


@pytest.mark.skipif(find_native_binary() is None, reason="meris-rs not built")
def test_rust_permissions_parity(workspace: Path, monkeypatch) -> None:
    monkeypatch.setenv("MERIS_NATIVE", "1")
    settings = {
        "permissions": {
            "allow": ["Bash(pytest*)", "Read"],
            "deny": ["Bash(rm -rf*)"],
        }
    }
    (workspace / ".meris").mkdir(exist_ok=True)
    (workspace / ".meris" / "settings.json").write_text(
        json.dumps(settings),
        encoding="utf-8",
    )
    args = {"command": "rm -rf /tmp/x"}
    py_err = check_tool_allowed("bash", args, settings, workspace=workspace)
    used, rs_err = native_check_tool_allowed(workspace, "bash", args)
    assert used is True
    assert (py_err is None) == (rs_err is None)
    if py_err:
        assert "denied" in py_err.lower()
        assert rs_err and "denied" in rs_err.lower()


@pytest.mark.skipif(find_native_binary() is None, reason="meris-rs not built")
def test_rust_sandbox_scan_parity() -> None:
    cases = [
        'pytest tests/ -m "not integration" -q',
        "pwd",
        "cd /tmp && find .",
    ]
    root = Path(__file__).resolve().parents[1]
    for cmd in cases:
        py_issues = scan_bash_command(cmd)
        proc = _meris_rs(
            "sandbox",
            "check",
            "--workspace",
            str(root),
            "--command",
            cmd,
            "--mode",
            "warn",
        )
        assert proc is not None and proc.returncode == 0
        data = json.loads(proc.stdout)
        rs_issues = [] if data.get("ok") else [data.get("message", "")]
        assert bool(py_issues) == bool(rs_issues)


@pytest.mark.skipif(find_native_binary() is None, reason="meris-rs not built")
def test_rust_sandbox_run_pytest(workspace: Path) -> None:
    (workspace / "AGENTS.md").write_text("# A\n", encoding="utf-8")
    proc = _meris_rs(
        "sandbox",
        "run",
        "--workspace",
        str(workspace),
        "--timeout",
        "30",
        "--",
        "python",
        "-c",
        "print(42)",
    )
    assert proc is not None
    assert proc.returncode == 0
    assert "42" in proc.stdout


def test_native_permissions_fallback_without_binary(workspace: Path, monkeypatch) -> None:
    monkeypatch.setenv("MERIS_NATIVE", "1")
    monkeypatch.setattr("meris.native.find_native_binary", lambda: None)
    used, err = native_check_tool_allowed(workspace, "bash", {"command": "pytest"})
    assert used is False
    assert err is None


def test_check_tool_allowed_python_when_native_off(workspace: Path) -> None:
    settings = {"permissions": {"allow": ["Read"], "deny": []}}
    err = check_tool_allowed("bash", {"command": "echo hi"}, settings, workspace=workspace)
    assert err is not None
