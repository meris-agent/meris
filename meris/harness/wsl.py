"""WSL detection for Windows hosts (bubblewrap sandbox lives in Linux)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Any


def probe_wsl_bwrap(*, timeout: int = 15) -> dict[str, Any]:
    """Return WSL + bwrap availability when running on Windows."""
    if sys.platform != "win32":
        return {"platform": sys.platform, "wslAvailable": False}

    wsl = shutil.which("wsl")
    if not wsl:
        return {
            "platform": "win32",
            "wslAvailable": False,
            "bwrapInWsl": False,
            "hint": "Install WSL2 for Linux bubblewrap sandbox (meris in WSL or wsl meris …)",
        }

    try:
        proc = subprocess.run(
            [wsl, "-e", "sh", "-lc", "command -v bwrap && bwrap --version 2>/dev/null | head -1"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {
            "platform": "win32",
            "wslAvailable": True,
            "bwrapInWsl": False,
            "hint": f"WSL probe failed: {e}",
        }

    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    bwrap_path = lines[0] if lines else None
    version = lines[1] if len(lines) > 1 else None
    if bwrap_path:
        return {
            "platform": "win32",
            "wslAvailable": True,
            "bwrapInWsl": True,
            "bwrapPath": bwrap_path,
            "bwrapVersion": version,
            "hint": "Run meris inside WSL for OS sandbox, or: wsl -e meris run …",
        }

    return {
        "platform": "win32",
        "wslAvailable": True,
        "bwrapInWsl": False,
        "hint": "WSL ok — install bubblewrap in WSL: sudo apt install bubblewrap",
    }
