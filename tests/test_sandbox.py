"""Bash sandbox policy tests."""

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
    assert "preset=" in sandbox.detail


def test_default_os_sandbox_auto(workspace: Path) -> None:
    settings = load_settings(workspace)
    from meris.harness.sandbox import get_os_sandbox_mode

    assert get_os_sandbox_mode(settings) == "auto"


def test_os_sandbox_off(workspace: Path) -> None:
    from meris.harness.sandbox import get_os_sandbox_mode, should_use_bubblewrap

    settings = {"sandbox": {"osSandbox": "off"}}
    assert get_os_sandbox_mode(settings) == "off"
    assert should_use_bubblewrap(settings) is False


def test_probe_os_sandbox(workspace: Path) -> None:
    from meris.harness.sandbox import probe_os_sandbox

    probe = probe_os_sandbox(workspace)
    assert probe["osSandbox"] in ("off", "auto", "require")
    assert probe["network"] in ("shared", "isolated", "allowlist")
    assert "wouldUseBubblewrap" in probe
    assert "maskedPaths" in probe


def test_collect_mask_paths(workspace: Path) -> None:
    from meris.harness.sandbox import collect_mask_paths

    (workspace / ".env").write_text("KEY=secret\n", encoding="utf-8")
    settings = {"sandbox": {"maskSecrets": True}}
    paths = collect_mask_paths(workspace, settings)
    assert any(p.name == ".env" for p in paths)
    settings_off = {"sandbox": {"maskSecrets": False}}
    assert collect_mask_paths(workspace, settings_off) == []


def test_bwrap_args_network_isolated(workspace: Path) -> None:
    from meris.harness.sandbox import bwrap_base_args, get_network_mode

    settings = {"sandbox": {"network": "isolated"}}
    assert get_network_mode(settings) == "isolated"
    args = bwrap_base_args(workspace, settings)
    assert "--unshare-net" in args
    assert "--share-net" not in args


def test_wsl_probe_non_windows() -> None:
    import sys

    from meris.harness.wsl import probe_wsl_bwrap

    if sys.platform == "win32":
        pytest.skip("Windows WSL probe tested manually")
    info = probe_wsl_bwrap()
    assert info.get("wslAvailable") is False


def test_run_bash_sync_plain(workspace: Path, monkeypatch) -> None:
    import sys

    from meris.harness.sandbox import run_bash_sync

    monkeypatch.setenv("MERIS_NATIVE", "0")
    settings = {"sandbox": {"osSandbox": "off", "bashTimeoutSec": 30}}
    cmd = "echo 99" if sys.platform == "win32" else 'python -c "print(99)"'
    out = run_bash_sync(workspace, cmd, settings)
    assert "99" in out
    assert out.startswith("exit=0")


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
