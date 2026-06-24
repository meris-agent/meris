"""P5-4 M5 — system prompt bridge + meris-rs run entry."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from meris.cli import app
from meris.harness.prompt_bridge import build_full_system_prompt


def test_build_full_system_prompt_includes_mode(workspace: Path) -> None:
    prompt = build_full_system_prompt(workspace, mode="ask")
    assert "MODE: ASK" in prompt
    assert "Meris" in prompt


def test_harness_system_prompt_json(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "harness",
            "system-prompt",
            "--cwd",
            str(workspace),
            "--mode",
            "plan",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    data = json.loads(result.stdout.strip())
    assert "prompt" in data
    assert "MODE: PLAN" in data["prompt"]


def test_harness_system_prompt_with_progress(workspace: Path) -> None:
    (workspace / "PROGRESS.md").write_text(
        "## Ratchet 摘要\n\n- item one\n",
        encoding="utf-8",
    )
    prompt = build_full_system_prompt(workspace, mode="run")
    assert "Progress (read first)" in prompt
    assert "item one" in prompt
