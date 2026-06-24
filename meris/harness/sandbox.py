"""Harness — bash sandbox policy."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SANDBOX_MODES = frozenset({"off", "warn", "strict"})
OS_SANDBOX_MODES = frozenset({"off", "auto", "require"})
NETWORK_MODES = frozenset({"shared", "isolated", "allowlist"})
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

_URL_HOST = re.compile(r"https?://([^/\s'\"#?]+)", re.I)
_GIT_SSH_HOST = re.compile(r"git@([^:/\s]+)", re.I)
_SSH_HOST = re.compile(r"\bssh\s+(?:[^\s@]+\@)?([^\s:/]+)", re.I)
_NETWORK_TOOL = re.compile(
    r"\b(curl|wget|pip\s+install|npm\s+install|git\s+clone|ssh)\b",
    re.I,
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
    """Resolved sandbox preset name (default workspace-write)."""
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


def get_network_allowlist(settings: dict) -> list[str]:
    """Host patterns: exact, suffix, or `*.example.com`."""
    raw = _sandbox_block(settings).get("networkAllowlist") or []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        pat = str(item).strip().lower()
        if pat and pat not in out:
            out.append(pat)
    return out


def get_effective_network_mode(settings: dict) -> str:
    """isolated + non-empty allowlist → allowlist (share-net + command checks)."""
    mode = get_network_mode(settings)
    if mode == "allowlist":
        return "allowlist"
    if mode == "isolated" and get_network_allowlist(settings):
        return "allowlist"
    return mode


def host_allowed(host: str, pattern: str) -> bool:
    host = host.lower().strip(".")
    pat = pattern.lower().strip()
    if not host or not pat:
        return False
    if pat.startswith("*."):
        base = pat[2:]
        return host == base or host.endswith("." + base)
    return host == pat or host.endswith("." + pat)


def extract_network_hosts(command: str) -> list[str]:
    cmd = command or ""
    seen: set[str] = set()
    hosts: list[str] = []
    for rx in (_URL_HOST, _GIT_SSH_HOST, _SSH_HOST):
        for m in rx.finditer(cmd):
            h = m.group(1).lower().strip(".")
            if h and h not in seen:
                seen.add(h)
                hosts.append(h)
    return hosts


def check_network_allowlist(command: str, settings: dict) -> str | None:
    """Return issue message when command violates allowlist; None if ok."""
    if get_effective_network_mode(settings) != "allowlist":
        return None
    allowlist = get_network_allowlist(settings)
    if not allowlist:
        return "network allowlist mode but sandbox.networkAllowlist is empty"
    if not _NETWORK_TOOL.search(command or ""):
        return None
    hosts = extract_network_hosts(command)
    if not hosts:
        return "network command without parseable host — not in networkAllowlist"
    for host in hosts:
        if not any(host_allowed(host, pat) for pat in allowlist):
            return f"host `{host}` not in sandbox.networkAllowlist"
    return None


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
    if get_effective_network_mode(settings) == "isolated":
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


def find_sandbox_exec() -> Path | None:
    """macOS Seatbelt helper (G6 spike — detection only, not enforced yet)."""
    if sys.platform != "darwin":
        return None
    found = shutil.which("sandbox-exec")
    return Path(found) if found else None


def should_use_seatbelt(settings: dict) -> bool:
    """True when macOS sandbox-exec should wrap bash (G6.2)."""
    if sys.platform != "darwin":
        return False
    mode = get_os_sandbox_mode(settings)
    if mode == "off":
        return False
    if mode == "require":
        return find_sandbox_exec() is not None
    return find_sandbox_exec() is not None


def _fetch_seatbelt_plan(workspace: Path, settings: dict) -> tuple[str, list[str]]:
    """Load Meris-generated SBPL from meris-rs (single source of truth)."""
    import json
    import subprocess

    from meris.native import find_native_binary

    binary = find_native_binary()
    if not binary:
        raise RuntimeError("seatbelt requires meris-rs binary for policy generation")

    cmd = [
        str(binary),
        "sandbox",
        "policy",
        "--workspace",
        str(workspace.resolve()),
        "--settings-json",
        json.dumps(settings),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(err or "meris-rs sandbox policy failed")
    data = json.loads(proc.stdout)
    return str(data["policy"]), list(data.get("params") or [])


def build_seatbelt_policy(workspace: Path, settings: dict) -> tuple[str, list[str]]:
    """Build SBPL via meris-rs MerisSeatbeltPlan."""
    return _fetch_seatbelt_plan(workspace, settings)


def _run_seatbelt_sync(
    workspace: Path,
    command: str,
    timeout: int,
    settings: dict,
) -> tuple[int, str]:
    sb = find_sandbox_exec()
    if not sb:
        return 1, "sandbox-exec not found"
    ws = workspace.resolve()
    policy, params = build_seatbelt_policy(ws, settings)
    cmd = [str(sb), "-p", policy, *params, "--", "sh", "-c", command]
    proc = subprocess.run(
        cmd,
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
        "network": get_effective_network_mode(settings),
        "networkAllowlist": get_network_allowlist(settings),
        "maskSecrets": get_mask_secrets(settings),
        "maskedPaths": [str(p) for p in collect_mask_paths(ws, settings)],
        "bubblewrap": str(bwrap) if bwrap else None,
        "bubblewrapVersion": None,
        "wouldUseBubblewrap": would,
        "sandboxExec": str(find_sandbox_exec()) if find_sandbox_exec() else None,
        "wouldUseSeatbelt": should_use_seatbelt(settings),
    }


def describe_platform_sandbox(workspace: Path, settings: dict) -> dict[str, Any]:
    """Summarize policy vs OS sandbox layers for doctor / platform matrix."""
    ws = workspace.resolve()
    probe = probe_os_sandbox(ws, settings)
    preset = get_sandbox_preset(settings)
    preset_tag = f"preset={preset}"
    plat = sys.platform
    os_mode = get_os_sandbox_mode(settings)
    would_bwrap = bool(probe.get("wouldUseBubblewrap"))
    has_bwrap = bool(probe.get("bubblewrap"))

    if plat == "linux":
        if would_bwrap:
            detail = f"linux: policy + bubblewrap active; {preset_tag}"
            status = "ok"
        elif has_bwrap and os_mode == "auto":
            detail = f"linux: policy only (bwrap present, osSandbox=auto inactive); {preset_tag}"
            status = "warn"
        elif os_mode == "require" and not has_bwrap:
            detail = f"linux: osSandbox=require but bwrap missing; {preset_tag}"
            status = "warn"
        else:
            detail = (
                f"linux: policy + cwd lock only — install bubblewrap for OS layer; {preset_tag}"
            )
            status = "warn"
        platform_gaps: list[str] = [] if would_bwrap else ["Linux OS sandbox inactive"]
    elif plat == "darwin":
        would_seatbelt = bool(probe.get("wouldUseSeatbelt"))
        seatbelt = find_sandbox_exec()
        if would_seatbelt:
            detail = f"macOS: policy + Seatbelt (sandbox-exec) active; {preset_tag}"
            status = "ok"
            platform_gaps = []
        elif seatbelt and os_mode != "off":
            detail = (
                f"macOS: sandbox-exec present but inactive — check osSandbox preset; {preset_tag}"
            )
            status = "warn"
            platform_gaps = ["Seatbelt not active"]
        else:
            detail = (
                f"macOS: policy + cwd lock only — install sandbox-exec / enable osSandbox; "
                f"{preset_tag}"
            )
            status = "warn"
            platform_gaps = ["no macOS Seatbelt sandbox"]
    elif plat == "win32":
        from meris.harness.wsl import probe_wsl_bwrap

        wsl = probe_wsl_bwrap()
        if wsl.get("bwrapInWsl"):
            detail = f"win32: policy on native; bubblewrap via WSL; {preset_tag}"
            status = "ok"
            platform_gaps = ["Windows native has no OS sandbox — use WSL for bwrap"]
        elif wsl.get("wslAvailable"):
            detail = (
                f"win32: policy + cwd only — install bwrap in WSL "
                f"(sudo apt install bubblewrap); {preset_tag}"
            )
            status = "warn"
            platform_gaps = ["Windows native has no OS sandbox"]
        else:
            detail = (
                f"win32: policy + cwd only — install WSL2 + bubblewrap for OS sandbox; "
                f"{preset_tag}"
            )
            status = "warn"
            platform_gaps = ["Windows native has no OS sandbox", "WSL2 not detected"]
    else:
        detail = f"{plat}: policy layer only; {preset_tag}"
        status = "warn"
        platform_gaps = ["unknown platform"]

    return {
        "platform": plat,
        "preset": preset,
        "policyLayer": True,
        "osLayerActive": would_bwrap,
        "platformGaps": platform_gaps,
        "status": status,
        "detail": detail,
        "probe": probe,
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

    verdict = check_bash_sandbox(workspace, command, settings)
    if verdict and verdict.blocked:
        return f"exit=1\n{verdict.message}"

    if native_enabled():
        native_out = native_run_bash(workspace, command, timeout=timeout)
        if native_out is not None:
            return native_out

    if os_mode == "require" and sys.platform == "linux" and not find_bubblewrap():
        return "exit=1\nsandbox.osSandbox=require but bubblewrap (bwrap) not found"
    if os_mode == "require" and sys.platform == "darwin" and not find_sandbox_exec():
        return "exit=1\nsandbox.osSandbox=require but sandbox-exec not found"

    try:
        if should_use_bubblewrap(settings):
            code, out = _run_bwrap_sync(workspace, command, timeout, settings)
        elif should_use_seatbelt(settings):
            code, out = _run_seatbelt_sync(workspace, command, timeout, settings)
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
    if native is not None and not native.get("ok"):
        blocked = bool(native.get("blocked"))
        message = str(native.get("message", ""))
        if blocked or mode == "warn":
            return SandboxVerdict(blocked=blocked, message=message, mode=mode)
        return None

    issues = scan_bash_command(command)
    net_issue = check_network_allowlist(command, settings)
    if net_issue:
        issues.insert(0, net_issue)
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
