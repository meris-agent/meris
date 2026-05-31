"""Harness — Feedback subsystem (Definition of Done + post-edit sensors)."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from meris.harness.settings import load_settings


def parse_dod_from_agents(workspace: Path) -> list[str]:
    """Extract shell commands from AGENTS.md 'Definition of Done' section."""
    agents = workspace / "AGENTS.md"
    if not agents.is_file():
        return []
    text = agents.read_text(encoding="utf-8")
    m = re.search(r"##\s*完成定义|##\s*Definition of Done", text, re.I)
    if not m:
        return []
    section = text[m.start() :]
    cmds = re.findall(r"^[-*]\s*`([^`]+)`", section, re.M)
    return cmds[:6]


async def _run_commands(workspace: Path, cmds: list[str], timeout: int = 300) -> tuple[bool, str]:
    if not cmds:
        return True, "(no commands)"
    outputs: list[str] = []
    for cmd in cmds:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        text = out.decode("utf-8", errors="replace")
        outputs.append(f"$ {cmd}\nexit={proc.returncode}\n{text[-2000:]}")
        if proc.returncode != 0:
            return False, "\n\n".join(outputs)
    return True, "\n\n".join(outputs)


async def run_sensors(workspace: Path, commands: list[str] | None = None) -> tuple[bool, str]:
    """Run DoD / onComplete commands."""
    cmds = commands
    if cmds is None:
        settings = load_settings(workspace)
        if not settings.get("sensors", {}).get("onComplete", True):
            return True, "(onComplete sensors disabled)"
        cmds = parse_dod_from_agents(workspace)
    return await _run_commands(workspace, cmds)


async def run_post_edit_sensors(workspace: Path) -> tuple[bool, str]:
    """Fast feedback loop after write/edit — Anthropic $191 pattern."""
    settings = load_settings(workspace)
    cmds = settings.get("sensors", {}).get("postEdit") or []
    if not cmds:
        return True, ""
    ok, out = await _run_commands(workspace, cmds, timeout=120)
    return ok, out
