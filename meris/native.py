"""Optional native (Rust) acceleration for harness primitives."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from meris.config import env_flag


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
    for p in candidate_binaries():
        if p.is_file():
            return p
    return None


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
    """Use native compress when MERIS_NATIVE=1 and binary exists; else Python."""
    from meris.harness.context import compress_messages

    if env_flag("NATIVE"):
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
