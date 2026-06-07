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
NETWORK_MODES = frozenset({"shared", "isolated"})
SANDBOX_PRESETS = frozenset({"read-only", "workspace-write", "danger-full-access"})
DEFAULT_MODE = "warn"
DEFAULT_OS_SANDBOX = "auto"
DEFAULT_NETWORK = "isolated"
DEFAULT_PRESET = "workspace-write"

_PRESET_VALUES: dict[str, dict[str, str]] = {
    "read-only": {"mode": "strict", "network": "isolated", "osSandbox": "auto"},
    "workspace-write": {"mode": "warn", "network": "isolated", "osSandbox": "auto"},
    "danger-full-access": {"mode": "off", "network": "shared", "osSandbox": "off"},
}

DEFAULT_BASH_TIMEOUT = 120

DEFAULT_MASK_REL: tuple[str, ...] = (
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
)

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


def _sandbox_block(settings: dict) -> dict:
    block = settings.get("sandbox")
    return block if isinstance(block, dict) else {}


def get_sandbox_preset(settings: dict) -> str:
    """Resolved Codex-style preset name (default workspace-write)."""
    raw = _sandbox_block(settings).get("preset", DEFAULT_PRESET)
    preset = str(raw).strip().lower()
    return preset if preset in SANDBOX_PRESETS else DEFAULT_PRESET


def _resolve_sandbox_field(
    settings: dict,
    field: str,
    *,
    valid: frozenset[str],
    hard_default: str,
) -> str:
    block = _sandbox_block(settings)
    if field in block:
        val = str(block[field]).strip().lower()
        if val in valid:
            return val
    preset = get_sandbox_preset(settings)
    from_preset = _PRESET_VALUES.get(preset, {}).get(field)
    if from_preset and from_preset in valid:
        return from_preset
    return hard_default


def get_sandbox_mode(settings: dict) -> str:
    return _resolve_sandbox_field(
        settings, "mode", valid=SANDBOX_MODES, hard_default=DEFAULT_MODE
    )


def get_bash_timeout(settings: dict) -> int:
    raw = (settings.get("sandbox") or {}).get("bashTimeoutSec", DEFAULT_BASH_TIMEOUT)
    try:
        sec = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_BASH_TIMEOUT
    return max(5, min(sec, 3600))


def get_os_sandbox_mode(settings: dict) -> str:
    return _resolve_sandbox_field(
        settings, "osSandbox", valid=OS_SANDBOX_MODES, hard_default=DEFAULT_OS_SANDBOX
    )


def get_network_mode(settings: dict) -> str:
    return _resolve_sandbox_field(
        settings, "network", valid=NETWORK_MODES, hard_default=DEFAULT_NETWORK
    )


def get_mask_secrets(settings: dict) -> bool:
    raw = (settings.get("sandbox") or {}).get("maskSecrets", True)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes")


def collect_mask_paths(workspace: Path, settings: dict) -> list[Path]:
    if not get_mask_secrets(settings):
        return []
    ws = workspace.resolve()
    rels: list[str] = list(DEFAULT_MASK_REL)
    extra = (settings.get("sandbox") or {}).get("maskPaths") or []
    if isinstance(extra, list):
        for item in extra:
            rel = str(item).strip().replace("\\", "/")
            if rel and rel not in rels:
                rels.append(rel)
    out: list[Path] = []
    for rel in rels:
        p = ws / rel
        if p.is_file():
            out.append(p)
    return out


def bwrap_base_args(workspace: Path, settings: dict) -> list[str]:
    ws = workspace.resolve()
    ws_s = str(ws)
    args = [
        "--ro-bind",
        "/",
        "/",
        "--bind",
        ws_s,
        ws_s,
    ]
    for mask in collect_mask_paths(ws, settings):
        args.extend(["--ro-bind", "/dev/null", str(mask)])
    args.extend(
        [
            "--tmpfs",
            "/tmp",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--die-with-parent",
            "--new-session",
            "--unshare-pid",
        ]
    )
    if get_network_mode(settings) == "isolated":
        args.append("--unshare-net")
    else:
        args.append("--share-net")
    args.extend(["--chdir", ws_s])
    return args


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
        if "maskedPaths" not in native:
            native["maskedPaths"] = [str(p) for p in collect_mask_paths(ws, settings)]
        return native
    bwrap = find_bubblewrap()
    os_mode = get_os_sandbox_mode(settings)
    would = should_use_bubblewrap(settings)
    if os_mode == "require" and not bwrap:
        would = False
    return {
        "platform": sys.platform,
        "osSandbox": os_mode,
        "network": get_network_mode(settings),
        "maskSecrets": get_mask_secrets(settings),
        "maskedPaths": [str(p) for p in collect_mask_paths(ws, settings)],
        "bubblewrap": str(bwrap) if bwrap else None,
        "bubblewrapVersion": None,
        "wouldUseBubblewrap": would,
    }


def _truncate_output(text: str, limit: int = 8000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _run_bwrap_sync(workspace: Path, command: str, timeout: int, settings: dict) -> tuple[int, str]:
    bwrap = find_bubblewrap()
    if not bwrap:
        return 1, "bubblewrap (bwrap) not found"
    proc = subprocess.run(
        [str(bwrap), *bwrap_base_args(workspace, settings), "sh", "-c", command],
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
            code, out = _run_bwrap_sync(workspace, command, timeout, settings)
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
