"""Harness — bash sandbox policy (Phase E3)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SANDBOX_MODES = frozenset({"off", "warn", "strict"})
DEFAULT_MODE = "warn"
DEFAULT_BASH_TIMEOUT = 120

# Exploratory / cwd-escape patterns — align with .meris/rules/bash-permissions.md
_BASH_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"/workspace\b", re.I), "forbidden path `/workspace` — cwd is already repo root"),
    (re.compile(r"(?:^|[;&|]\s*|\s&&\s*)cd\s", re.I), "`cd` blocked — cwd is locked to workspace"),
    (re.compile(r"\bfind\s", re.I), "`find` blocked — use glob / grep / read_file"),
    (re.compile(r"\bpwd\b", re.I), "`pwd` blocked — use glob for pyproject.toml"),
    (re.compile(r"(?:^|[;&|]\s*|\s&&\s*)ls(?:\s|$)", re.I), "`ls` blocked — use glob / read_file"),
)


@dataclass(frozen=True)
class SandboxVerdict:
    blocked: bool
    message: str
    mode: str


def get_sandbox_mode(settings: dict) -> str:
    raw = (settings.get("sandbox") or {}).get("mode", DEFAULT_MODE)
    mode = str(raw).strip().lower()
    return mode if mode in SANDBOX_MODES else DEFAULT_MODE


def get_bash_timeout(settings: dict) -> int:
    raw = (settings.get("sandbox") or {}).get("bashTimeoutSec", DEFAULT_BASH_TIMEOUT)
    try:
        sec = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_BASH_TIMEOUT
    return max(5, min(sec, 3600))


def scan_bash_command(command: str) -> list[str]:
    """Return human-readable issues for a bash command string."""
    cmd = (command or "").strip()
    if not cmd:
        return []
    issues: list[str] = []
    for rx, hint in _BASH_RULES:
        if rx.search(cmd):
            issues.append(hint)
    return issues


def check_bash_sandbox(
    workspace: Path,
    command: str,
    settings: dict,
) -> SandboxVerdict | None:
    """None if allowed silently; verdict if warn or block."""
    _ = workspace.resolve()
    mode = get_sandbox_mode(settings)
    if mode == "off":
        return None

    from meris.native import native_sandbox_check

    native = native_sandbox_check(workspace, command, mode)
    if native is not None:
        if native.get("ok"):
            return None
        blocked = bool(native.get("blocked"))
        message = str(native.get("message", ""))
        if blocked or mode == "warn":
            return SandboxVerdict(blocked=blocked, message=message, mode=mode)
        return None

    issues = scan_bash_command(command)
    if not issues:
        return None
    msg = issues[0]
    if mode == "strict":
        return SandboxVerdict(
            blocked=True,
            message=f"Sandbox (strict): {msg}. Use glob/read_file/pytest per .meris/rules/bash-permissions.md",
            mode=mode,
        )
    return SandboxVerdict(
        blocked=False,
        message=f"{msg} (sandbox mode=warn — allowed but discouraged)",
        mode=mode,
    )
