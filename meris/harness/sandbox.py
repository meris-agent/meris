"""Harness — bash sandbox policy (Phase E3)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SANDBOX_MODES = frozenset({"off", "warn", "strict"})
OS_SANDBOX_MODES = frozenset({"off", "auto", "require"})
DEFAULT_MODE = "warn"
DEFAULT_OS_SANDBOX = "auto"
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


def get_os_sandbox_mode(settings: dict) -> str:
    raw = (settings.get("sandbox") or {}).get("osSandbox", DEFAULT_OS_SANDBOX)
    mode = str(raw).strip().lower()
    return mode if mode in OS_SANDBOX_MODES else DEFAULT_OS_SANDBOX


def find_bubblewrap() -> Path | None:
    if sys.platform != "linux":
        return None
    for name in ("bwrap", "bubblewrap"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def should_use_bubblewrap(settings: dict) -> bool:
    if sys.platform != "linux":
        return False
    mode = get_os_sandbox_mode(settings)
    if mode == "off":
        return False
    bwrap = find_bubblewrap()
    if mode == "require":
        return bwrap is not None
    return mode == "auto" and bwrap is not None


def probe_os_sandbox(workspace: Path, settings: dict | None = None) -> dict:
    """Bubblewrap / OS sandbox availability (prefers meris-rs probe when built)."""
    from meris.harness.settings import load_settings
    from meris.native import native_os_sandbox_probe

    ws = workspace.resolve()
    settings = settings or load_settings(ws)
    native = native_os_sandbox_probe(ws)
    if native is not None:
        return native
    bwrap = find_bubblewrap()
    os_mode = get_os_sandbox_mode(settings)
    would = should_use_bubblewrap(settings)
    if os_mode == "require" and not bwrap:
        would = False
    return {
        "platform": sys.platform,
        "osSandbox": os_mode,
        "bubblewrap": str(bwrap) if bwrap else None,
        "bubblewrapVersion": None,
        "wouldUseBubblewrap": would,
    }


def _truncate_output(text: str, limit: int = 8000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _run_bwrap_sync(workspace: Path, command: str, timeout: int) -> tuple[int, str]:
    bwrap = find_bubblewrap()
    if not bwrap:
        return 1, "bubblewrap (bwrap) not found"
    ws = workspace.resolve()
    ws_s = str(ws)
    proc = subprocess.run(
        [
            str(bwrap),
            "--ro-bind",
            "/",
            "/",
            "--bind",
            ws_s,
            ws_s,
            "--tmpfs",
            "/tmp",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--die-with-parent",
            "--new-session",
            "--unshare-pid",
            "--share-net",
            "--chdir",
            ws_s,
            "sh",
            "-c",
            command,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    code = proc.returncode if proc.returncode is not None else 1
    return code, _truncate_output(out.strip())


def _run_plain_sync(workspace: Path, command: str, timeout: int) -> tuple[int, str]:
    ws = workspace.resolve()
    if os.name == "nt":
        proc = subprocess.run(
            ["cmd", "/C", command],
            cwd=ws,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    else:
        proc = subprocess.run(
            ["sh", "-c", command],
            cwd=ws,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    out = (proc.stdout or "") + (proc.stderr or "")
    code = proc.returncode if proc.returncode is not None else 1
    return code, _truncate_output(out.strip())


def run_bash_sync(workspace: Path, command: str, settings: dict) -> str:
    """Run bash with policy backend (native → bwrap → plain cwd lock)."""
    from meris.native import native_enabled, native_run_bash

    timeout = get_bash_timeout(settings)
    os_mode = get_os_sandbox_mode(settings)

    if native_enabled():
        native_out = native_run_bash(workspace, command, timeout=timeout)
        if native_out is not None:
            return native_out

    if os_mode == "require" and sys.platform == "linux" and not find_bubblewrap():
        return "exit=1\nsandbox.osSandbox=require but bubblewrap (bwrap) not found"

    try:
        if should_use_bubblewrap(settings):
            code, out = _run_bwrap_sync(workspace, command, timeout)
        else:
            code, out = _run_plain_sync(workspace, command, timeout)
    except subprocess.TimeoutExpired:
        return f"exit=1\ntimeout after {timeout}s"
    text = out.strip() if out else ""
    return f"exit={code}\n{text}" if text else f"exit={code}"


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
