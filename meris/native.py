"""Optional native (Rust) acceleration for harness primitives."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from meris.config import env_tri


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def candidate_binaries() -> list[Path]:
    root = _repo_root()
    names = ["meris-rs.exe", "meris-rs"] if os.name == "nt" else ["meris-rs"]
    paths: list[Path] = []
    for profile in ("release", "debug"):
        for name in names:
            paths.append(root / "meris-rs" / "target" / profile / name)
    which = shutil.which("meris-rs")
    if which:
        paths.append(Path(which))
    return paths


def find_native_binary() -> Path | None:
    existing = [p for p in candidate_binaries() if p.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def native_enabled() -> bool:
    """Use meris-rs when MERIS_NATIVE=1, or auto when binary exists (opt out with MERIS_NATIVE=0)."""
    tri = env_tri("NATIVE")
    if tri is False:
        return False
    if tri is True:
        return True
    return find_native_binary() is not None


def native_status() -> dict[str, Any]:
    binary = find_native_binary()
    version = None
    if binary:
        try:
            out = subprocess.run(
                [str(binary), "version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            version = (out.stdout or out.stderr).strip()
        except OSError:
            version = None
    return {
        "available": binary is not None,
        "binary": str(binary) if binary else None,
        "version": version,
        "source": str(_repo_root() / "meris-rs"),
    }


def build_native(*, release: bool = True) -> tuple[int, str]:
    """Run cargo build in meris-rs/. Returns (exit_code, combined output)."""
    cargo = shutil.which("cargo")
    if not cargo:
        return 1, "cargo not found — install Rust: https://rustup.rs"
    cmd = [cargo, "build"]
    if release:
        cmd.append("--release")
    proc = subprocess.run(
        cmd,
        cwd=_repo_root() / "meris-rs",
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def native_compress_messages(
    messages: list[dict[str, Any]],
    *,
    max_messages: int = 48,
    max_tokens: int | None = None,
    max_tool_tokens: int = 2000,
) -> list[dict[str, Any]] | None:
    """Compress via meris-rs; returns None if native unavailable or fails."""
    binary = find_native_binary()
    if not binary:
        return None
    cmd = [
        str(binary),
        "context",
        "compress",
        "--max-messages",
        str(max_messages),
        "--max-tool-tokens",
        str(max_tool_tokens),
    ]
    if max_tokens is not None:
        cmd.extend(["--max-tokens", str(max_tokens)])
    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(messages, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        return None
    return None


def compress_messages_auto(
    messages: list[dict[str, Any]],
    *,
    max_messages: int = 48,
    max_tokens: int | None = None,
    max_tool_tokens: int = 2000,
) -> list[dict[str, Any]]:
    """Use native compress when enabled and binary exists; else Python."""
    from meris.harness.context import compress_messages

    if native_enabled():
        native = native_compress_messages(
            messages,
            max_messages=max_messages,
            max_tokens=max_tokens,
            max_tool_tokens=max_tool_tokens,
        )
        if native is not None:
            return native
    return compress_messages(
        messages,
        max_messages=max_messages,
        max_tokens=max_tokens,
        max_tool_tokens=max_tool_tokens,
    )


def _run_native(
    args: list[str],
    *,
    timeout: int = 30,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str] | None:
    binary = find_native_binary()
    if not binary:
        return None
    try:
        return subprocess.run(
            [str(binary), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def native_check_tool_allowed(
    workspace: Path,
    tool_name: str,
    args: dict[str, Any],
) -> tuple[bool, str | None]:
    """(used_native, error). used_native=False → fall back to Python check."""
    if not native_enabled():
        return False, None
    if find_native_binary() is None:
        return False, None
    proc = _run_native(
        [
            "permissions",
            "--workspace",
            str(workspace.resolve()),
            "--tool",
            tool_name,
            "--args",
            json.dumps(args, ensure_ascii=False),
        ],
        timeout=10,
    )
    if proc is None:
        return False, None
    if proc.returncode == 0:
        return True, None
    err = (proc.stderr or proc.stdout or "").strip()
    return True, err or "Permission denied (native)"


def native_sandbox_check(
    workspace: Path,
    command: str,
    mode: str,
) -> dict[str, Any] | None:
    """Parse meris-rs sandbox check JSON; None if native unavailable."""
    if not native_enabled():
        return None
    proc = _run_native(
        [
            "sandbox",
            "check",
            "--workspace",
            str(workspace.resolve()),
            "--command",
            command,
            "--mode",
            mode,
        ],
        timeout=10,
    )
    if proc is None or not proc.stdout.strip():
        return None
    try:
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None


def native_os_sandbox_probe(workspace: Path) -> dict[str, Any] | None:
    """JSON from meris-rs sandbox probe; None if binary unavailable."""
    proc = _run_native(
        ["sandbox", "probe", "--workspace", str(workspace.resolve())],
        timeout=10,
    )
    if proc is None or not proc.stdout.strip():
        return None
    try:
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None


def native_run_bash(
    workspace: Path,
    command: str,
    *,
    timeout: int = 120,
) -> str | None:
    """Run bash via meris-rs sandbox run; None if native unavailable."""
    if not native_enabled():
        return None
    proc = _run_native(
        [
            "sandbox",
            "run",
            "--workspace",
            str(workspace.resolve()),
            "--timeout",
            str(timeout),
            "--",
            command,
        ],
        timeout=timeout + 15,
    )
    if proc is None:
        return None
    out = (proc.stdout or "") + (proc.stderr or "")
    if not out.strip() and proc.returncode != 0:
        return f"exit={proc.returncode}\n(native sandbox failed)"
    return out.strip() or f"exit={proc.returncode}"
