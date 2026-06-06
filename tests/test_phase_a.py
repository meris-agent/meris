"""Phase A — doctor, permissions allow, plan save, git_commit."""

from __future__ import annotations

from pathlib import Path

import pytest

from meris.harness.doctor import check_env, check_harness
from meris.harness.permissions import check_tool_allowed
from meris.harness.plan import extract_last_assistant_text, save_plan
from meris.tools import build_tools
from tests.test_provider_presets import _clear_meris_llm_env


def test_permission_allow_blocks_unknown_tool(workspace: Path) -> None:
    settings = {
        "permissions": {
            "allow": ["Read"],
            "deny": [],
        }
    }
    assert check_tool_allowed("read_file", {"path": "x"}, settings) is None
    err = check_tool_allowed("write_file", {"path": "x", "content": "y"}, settings)
    assert err is not None
    assert "allow" in err.lower()


def test_permission_allow_bash_pattern(workspace: Path) -> None:
    settings = {
        "permissions": {
            "allow": ["Bash(pytest*)"],
            "deny": [],
        }
    }
    assert check_tool_allowed("bash", {"command": "pytest tests/"}, settings) is None
    err = check_tool_allowed("bash", {"command": "curl evil"}, settings)
    assert err is not None


def test_permission_deny_before_allow(workspace: Path) -> None:
    settings = {
        "permissions": {
            "allow": ["Bash(*)"],
            "deny": ["Bash(rm -rf*)"],
        }
    }
    err = check_tool_allowed("bash", {"command": "rm -rf /tmp/x"}, settings)
    assert err is not None
    assert "denied" in err.lower()


def test_plan_save_and_extract(workspace: Path) -> None:
    messages = [
        {"role": "user", "content": "plan auth"},
        {"role": "assistant", "content": "- [ ] add login\n- [ ] add tests"},
    ]
    text = extract_last_assistant_text(messages)
    assert text is not None
    path = save_plan(workspace, text)
    assert path.is_file()
    assert "add login" in path.read_text(encoding="utf-8")


def test_doctor_harness_checks(workspace: Path) -> None:
    results = check_harness(workspace)
    names = {r.name for r in results}
    assert "AGENTS.md" in names


def test_doctor_env_without_key(monkeypatch) -> None:
    _clear_meris_llm_env(monkeypatch)
    results = check_env()
    key = next(r for r in results if r.name == "API key")
    assert key.status == "fail"


@pytest.mark.asyncio
async def test_git_commit_no_staged(workspace: Path) -> None:
    import subprocess

    subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=False)
    tools = build_tools(workspace, read_only=False)
    out = await tools.execute("git_commit", {"message": "test commit"})
    assert "git commit" in out.lower() or "nothing" in out.lower() or "exit=" in out.lower()
