"""Phase E3 — bash sandbox."""

from __future__ import annotations

from pathlib import Path

import pytest

from meris.harness.doctor import check_harness
from meris.harness.sandbox import (
    check_bash_sandbox,
    get_bash_timeout,
    get_sandbox_mode,
    scan_bash_command,
)
from meris.harness.settings import load_settings


def test_default_sandbox_mode(workspace: Path) -> None:
    settings = load_settings(workspace)
    assert get_sandbox_mode(settings) == "warn"
    assert get_bash_timeout(settings) == 120


def test_scan_blocks_exploratory_bash() -> None:
    issues = scan_bash_command("cd /tmp && find . -name foo")
    assert any("cd" in i for i in issues)
    assert any("find" in i for i in issues)


def test_scan_allows_pytest() -> None:
    assert not scan_bash_command('pytest tests/ -m "not integration" -q')


def test_strict_blocks_cd(workspace: Path) -> None:
    settings = {"sandbox": {"mode": "strict"}}
    verdict = check_bash_sandbox(workspace, "pwd", settings)
    assert verdict is not None
    assert verdict.blocked is True
    assert "strict" in verdict.message


def test_warn_allows_cd_with_message(workspace: Path) -> None:
    settings = {"sandbox": {"mode": "warn"}}
    verdict = check_bash_sandbox(workspace, "pwd", settings)
    assert verdict is not None
    assert verdict.blocked is False


def test_off_skips_sandbox(workspace: Path) -> None:
    settings = {"sandbox": {"mode": "off"}}
    assert check_bash_sandbox(workspace, "pwd", settings) is None


def test_doctor_reports_sandbox(workspace: Path) -> None:
    results = check_harness(workspace)
    sandbox = next(r for r in results if r.name == "sandbox")
    assert sandbox.status == "ok"
    assert "mode=" in sandbox.detail


@pytest.mark.asyncio
async def test_loop_strict_blocks_bash(workspace: Path, monkeypatch) -> None:
    from meris.loop import agent_loop
    from meris.provider import Provider

    class FakeProvider(Provider):
        model = "fake"

        def __init__(self) -> None:
            self._turn = 0

        async def chat(self, messages, tools=None):
            self._turn += 1
            if self._turn == 1:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "tc1",
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "arguments": '{"command": "pwd"}',
                            },
                        }
                    ],
                }
            return {"content": "done"}

    (workspace / ".meris" / "settings.yaml").write_text(
        "sandbox:\n  mode: strict\npermissions:\n  allow:\n    - Bash(*)\n  deny: []\n",
        encoding="utf-8",
    )

    lines: list[str] = []
    async for line in agent_loop(
        workspace,
        "run pwd",
        mode="run",
        provider=FakeProvider(),
        max_turns=3,
        run_sensors_at_end=False,
    ):
        lines.append(line)

    joined = "\n".join(lines)
    assert "SANDBOX" in joined or "Sandbox (strict)" in joined
