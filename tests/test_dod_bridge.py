"""DoD failure ratchet bridge."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from meris.cli import app
from meris.harness.dod_bridge import handle_dod_failed


def test_dod_bridge_harness_check_kind(workspace: Path) -> None:
    result = handle_dod_failed(
        workspace,
        session="sess01",
        task="fix paths",
        mode="run",
        sensor_out="harness check failed: paths:readme",
    )
    assert result["kind"] == "harness_check_fail"
    assert result["hints"]


def test_harness_dod_failed_json(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "harness",
            "dod-failed",
            "--cwd",
            str(workspace),
            "--session",
            "abc",
            "--task",
            "t",
            "--detail",
            "sensor fail",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    data = json.loads(result.stdout.strip())
    assert data["recorded"] is True
    assert "hints" in data
    assert any("ratchet" in str(h).lower() for h in data["hints"])
