"""Harness — Feedback subsystem (Definition of Done + post-edit sensors)."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from meris.harness.settings import load_settings


def _extract_dod_section(text: str) -> str:
    m = re.search(r"##\s*完成定义|##\s*Definition of Done", text, re.I)
    if not m:
        return ""
    rest = text[m.start() :]
    nxt = re.search(r"\n##\s+", rest[m.end() - m.start() :])
    if nxt:
        return rest[: m.end() - m.start() + nxt.start()]
    return rest


def parse_dod_from_agents(workspace: Path) -> list[str]:
    """Extract shell commands from AGENTS.md DoD (list items or ```bash blocks)."""
    agents = workspace / "AGENTS.md"
    if not agents.is_file():
        return []
    section = _extract_dod_section(agents.read_text(encoding="utf-8"))
    if not section:
        return []

    cmds: list[str] = []
    cmds.extend(re.findall(r"^[-*]\s*`([^`]+)`", section, re.M))
    fence = re.search(r"```(?:bash|sh|shell)?\s*\n(.*?)```", section, re.S | re.I)
    if fence:
        for line in fence.group(1).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                cmds.append(line)

    seen: set[str] = set()
    out: list[str] = []
    for c in cmds:
        c = c.strip()
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out[:8]


def format_dod_failure_detail(output: str) -> str:
    """Ratchet-friendly sensor output with remediation hints."""
    lines = [output.strip()[:1800]]
    lower = output.lower()
    hints: list[str] = []
    if "import:forge" in lower or "forge/" in lower:
        hints.append("Run: meris harness check — remove forge/ imports; use from meris....")
    if "paths:readme" in lower or "meris/readme" in lower:
        hints.append("Use README.md at repo root — read .meris/rules/paths.md")
    if "pytest" in lower and "exit=" in lower:
        hints.append('Fix failing tests: pytest tests/ -m "not integration" -q')
    if "harness check" in lower or "meris harness" in lower:
        hints.append("Run: meris harness check — fix static harness violations")
    if hints:
        lines.append("hints:")
        lines.extend(f"- {h}" for h in hints)
    return "\n".join(lines)


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
    ok, out = await _run_commands(workspace, cmds)
    if not ok:
        return False, format_dod_failure_detail(out)
    return ok, out


async def run_post_edit_sensors(workspace: Path) -> tuple[bool, str]:
    """Fast feedback loop after write/edit — Anthropic $191 pattern."""
    settings = load_settings(workspace)
    cmds = settings.get("sensors", {}).get("postEdit") or []
    if not cmds:
        return True, ""
    ok, out = await _run_commands(workspace, cmds, timeout=120)
    if not ok:
        return False, format_dod_failure_detail(out)
    return ok, out
