"""P5-4 M4 — hooks bridge, events, plan for native agent."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from meris.cli import app
from meris.harness.hooks import HookResult


def test_hook_pre_json_no_hooks(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "harness",
            "hook",
            "pre",
            "--cwd",
            str(workspace),
            "--tool",
            "read_file",
            "--args",
            '{"path":"x"}',
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    data = json.loads(result.stdout.strip())
    assert data["block"] is False


def test_hook_on_save_json(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "harness",
            "hook",
            "on-save",
            "--cwd",
            str(workspace),
            "--path",
            "foo.py",
            "--json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert "block" in data


def test_ratchet_record_json(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "harness",
            "ratchet-record",
            "--cwd",
            str(workspace),
            "--kind",
            "permission_denied",
            "--detail",
            "test block",
            "--tool",
            "bash",
            "--json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert "ok" in data


def test_hooks_bridge_helpers() -> None:
    from meris.harness.hooks_bridge import hook_result_json

    s = hook_result_json(HookResult(block=False, message="ok"))
    assert json.loads(s)["message"] == "ok"
