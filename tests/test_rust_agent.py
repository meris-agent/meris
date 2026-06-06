"""P5-4 M1 — native agent session + loop wiring."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from meris.harness.sessions import SessionRecord, load_session, save_session
from meris.native import find_native_binary, native_loop_enabled


@pytest.mark.skipif(find_native_binary() is None, reason="meris-rs not built")
def test_agent_session_show_roundtrip(workspace: Path) -> None:
    rec = SessionRecord(
        id="abc123test01",
        task="parity check",
        mode="ask",
        workspace=str(workspace.resolve()),
        messages=[{"role": "user", "content": "hi"}],
    )
    save_session(workspace, rec)
    binary = find_native_binary()
    proc = subprocess.run(
        [
            str(binary),
            "agent",
            "session",
            "show",
            "--workspace",
            str(workspace.resolve()),
            "--id",
            rec.id,
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if proc.returncode != 0 and "unrecognized subcommand 'agent'" in (proc.stderr or proc.stdout):
        pytest.skip("meris-rs agent subcommand not in binary")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    data = json.loads(proc.stdout)
    assert data["id"] == rec.id
    assert data["task"] == "parity check"
    loaded = load_session(workspace, rec.id)
    assert loaded is not None
    assert loaded.messages[0]["content"] == "hi"


def test_native_loop_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MERIS_NATIVE_LOOP", raising=False)
    assert native_loop_enabled() is False


@pytest.mark.skipif(find_native_binary() is None, reason="meris-rs not built")
def test_native_loop_opt_in(monkeypatch) -> None:
    binary = find_native_binary()
    probe = subprocess.run(
        [str(binary), "agent", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip("agent subcommand not in binary")
    monkeypatch.setenv("MERIS_NATIVE_LOOP", "1")
    assert native_loop_enabled() is True


def test_tool_schemas_parity_script() -> None:
    import sys

    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "scripts/check_tool_schemas_parity.py"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if find_native_binary() is None:
        assert proc.returncode == 0
        assert "skip" in proc.stdout
        return
    probe = subprocess.run(
        [str(find_native_binary()), "tools", "schemas", "--read-only"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip("tools schemas not in binary")
    assert proc.returncode == 0, proc.stdout + proc.stderr
