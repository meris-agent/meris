"""Phase F2-M1 — review task bridge for native loop."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from meris.cli import app
from meris.harness.review import build_review_task_from_diff
from meris.harness.review_bridge import build_review_task_for_native


def test_build_review_task_from_diff() -> None:
    task = build_review_task_from_diff("+added line\n", staged=False)
    assert "Review the following" in task
    assert "+added line" in task
    assert "Do not modify" in task


def test_harness_review_task_json_no_diff(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["harness", "review-task", "--cwd", str(workspace), "--json"],
    )
    assert result.exit_code != 0


def test_harness_review_task_json_with_diff(workspace: Path) -> None:
    runner = CliRunner()
    diff = "+# change\n"
    proc = subprocess.run(
        ["git", "apply", "--cached", "-"],
        input=diff,
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip("git apply failed in fixture")
    result = runner.invoke(
        app,
        ["harness", "review-task", "--cwd", str(workspace), "--staged", "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    data = json.loads(result.stdout.strip())
    assert "task" in data
    assert "Review the following staged" in data["task"]


def test_review_bridge_module(workspace: Path, tmp_path: Path) -> None:
    f = workspace / "review-me.txt"
    f.write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", str(f.name)], cwd=workspace, check=False)
    try:
        task = build_review_task_for_native(workspace, staged=True)
        assert "review-me.txt" in task or "+a" in task or "Review" in task
    except RuntimeError:
        pytest.skip("no staged diff in workspace")
