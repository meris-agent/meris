"""Optional native (Rust) acceleration for harness primitives."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable, Union

from meris.config import env_get, env_tri

ApproveFn = Callable[[str, dict], Union[bool, Awaitable[bool]]]


def _subprocess_run(*popenargs, **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run with UTF-8 text mode (avoids GBK decode errors on Windows)."""
    if kwargs.get("text") or kwargs.get("capture_output"):
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return subprocess.run(*popenargs, **kwargs)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _bundled_dir() -> Path:
    return Path(__file__).resolve().parent / "_bundled"


def _bundled_binary_names() -> list[str]:
    if os.name == "nt":
        return ["meris-rs.exe", "meris-rs"]
    return ["meris-rs"]


def _bundled_candidates() -> list[Path]:
    bundled = _bundled_dir()
    return [bundled / name for name in _bundled_binary_names()]


def candidate_binaries() -> list[Path]:
    root = _repo_root()
    names = ["meris-rs.exe", "meris-rs"] if os.name == "nt" else ["meris-rs"]
    paths: list[Path] = []
    paths.extend(_bundled_candidates())
    for profile in ("release", "debug"):
        for name in names:
            paths.append(root / "meris-rs" / "target" / profile / name)
    which = shutil.which("meris-rs")
    if which:
        paths.append(Path(which))
    return paths


def _binary_source(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        resolved = path.resolve()
    except OSError:
        return "path"
    bundled = _bundled_dir()
    try:
        if resolved.parent == bundled.resolve() or bundled.resolve() in resolved.parents:
            return "bundled"
    except OSError:
        pass
    root = _repo_root()
    try:
        if root.resolve() in resolved.parents and "meris-rs" in str(resolved):
            return "dev"
    except OSError:
        pass
    return "path"


def find_native_binary() -> Path | None:
    for p in _bundled_candidates():
        if p.is_file():
            return p
    existing = [p for p in candidate_binaries() if p.is_file() and p not in _bundled_candidates()]
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


def native_provider_enabled() -> bool:
    """Use meris-rs for LLM chat when enabled (inherits MERIS_NATIVE auto unless MERIS_NATIVE_PROVIDER set)."""
    tri = env_tri("NATIVE_PROVIDER")
    if tri is False:
        return False
    if tri is True:
        return find_native_binary() is not None
    return native_enabled()


def native_status() -> dict[str, Any]:
    binary = find_native_binary()
    version = None
    if binary:
        try:
            out = _subprocess_run(
                [str(binary), "version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            version = (out.stdout or out.stderr).strip()
        except OSError:
            version = None
    source = _binary_source(binary)
    return {
        "available": binary is not None,
        "binary": str(binary) if binary else None,
        "version": version,
        "source": source or str(_repo_root() / "meris-rs"),
        "binarySource": source,
        "nativeEnabled": native_enabled(),
        "nativeProviderEnabled": native_provider_enabled(),
        "nativeLoopEnabled": native_loop_enabled(),
    }


def build_native(*, release: bool = True) -> tuple[int, str]:
    """Run cargo build in meris-rs/. Returns (exit_code, combined output)."""
    cargo = shutil.which("cargo")
    if not cargo:
        return 1, "cargo not found — install Rust: https://rustup.rs"
    cmd = [cargo, "build"]
    if release:
        cmd.append("--release")
    proc = _subprocess_run(
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
        proc = _subprocess_run(
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
        return _subprocess_run(
            [str(binary), *args],
            capture_output=True,
            text=True,
            input=input_text,
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


NATIVE_BUILTIN_TOOLS = frozenset({"read_file", "glob", "grep", "write_file", "edit_file", "bash"})
NATIVE_READONLY_TOOLS = frozenset({"read_file", "glob", "grep"})


def native_run_tool(workspace: Path, tool: str, args: dict[str, Any]) -> str | None:
    """Execute read_file/glob/grep/bash via meris-rs; None if unavailable."""
    if not native_enabled() or tool not in NATIVE_BUILTIN_TOOLS:
        return None
    if find_native_binary() is None:
        return None
    proc = _run_native(
        [
            "tools",
            "run",
            "--workspace",
            str(workspace.resolve()),
            "--tool",
            tool,
            "--args",
            json.dumps(args, ensure_ascii=False),
        ],
        timeout=60,
    )
    if proc is None or proc.returncode != 0:
        return None
    out = (proc.stdout or "").strip()
    return out or None


def _binary_supports_subcommand(sub: str) -> bool:
    binary = find_native_binary()
    if not binary:
        return False
    try:
        proc = _subprocess_run(
            [str(binary), sub, "--help"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError:
        return False
    return proc.returncode == 0


def native_tool_schemas(*, read_only: bool = False) -> list[dict[str, Any]] | None:
    """OpenAI function schemas from meris-rs tools schemas."""
    if not native_enabled() or not _binary_supports_subcommand("tools"):
        return None
    args = ["tools", "schemas"]
    if read_only:
        args.append("--read-only")
    proc = _run_native(args, timeout=10)
    if proc is None or proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        return None
    return None


def native_loop_enabled() -> bool:
    """Run agent loop in meris-rs when MERIS_NATIVE_LOOP=1 or =auto."""
    if not _binary_supports_subcommand("agent"):
        return False
    val = env_get("NATIVE_LOOP", "").strip().lower()
    if val in ("0", "false", "no"):
        return False
    if val in ("1", "true", "yes"):
        return True
    if val == "auto":
        return native_enabled()
    return False


async def stream_native_agent_loop(
    workspace: Path,
    task: str,
    *,
    mode: str = "ask",
    max_turns: int = 30,
    session_id: str | None = None,
    resume: bool = False,
    require_approval: bool = False,
    run_sensors_at_end: bool = True,
    approve_fn: ApproveFn | None = None,
    event_stream_path: str | Path | None = None,
    save_plan: bool = False,
    plan_output: str | None = None,
):
    """Yield progress lines from meris-rs agent run (async iterator)."""
    binary = find_native_binary()
    if not binary:
        return
    cmd = [
        str(binary),
        "agent",
        "run",
        "--workspace",
        str(workspace.resolve()),
        "--task",
        task,
        "--mode",
        mode,
        "--max-turns",
        str(max_turns),
    ]
    if session_id:
        cmd.extend(["--session-id", session_id])
    if resume:
        cmd.append("--resume")
    if require_approval:
        cmd.append("--require-approval")
    if not run_sensors_at_end:
        cmd.append("--no-sensor")
    if event_stream_path:
        cmd.extend(["--event-stream", str(event_stream_path)])
    if save_plan:
        cmd.append("--save-plan")
        if plan_output and plan_output != "__default__":
            cmd.extend(["--plan-output", plan_output])
        elif plan_output == "__default__":
            cmd.extend(["--plan-output", "__default__"])
    stdin_pipe = asyncio.subprocess.PIPE if require_approval else None
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        stdin=stdin_pipe,
    )
    assert proc.stdout is not None

    async def _respond_approval(line: str) -> None:
        if not require_approval or proc.stdin is None:
            return
        payload = json.loads(line.removeprefix("@meris-approve ").strip())
        tool = payload.get("tool", "")
        args = payload.get("args") or {}
        approved = False
        if approve_fn is not None:
            result = approve_fn(tool, args)
            if inspect.isawaitable(result):
                approved = await result
            else:
                approved = bool(result)
        proc.stdin.write((json.dumps({"approved": approved}) + "\n").encode("utf-8"))
        await proc.stdin.drain()

    async for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip("\n\r")
        if not line:
            continue
        if line.startswith("@meris-approve "):
            await _respond_approval(line)
            continue
        yield line
    await proc.wait()


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


def native_provider_chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    base_url: str,
    model: str,
    *,
    timeout: int = 120,
) -> dict[str, Any] | None:
    """Call meris-rs provider chat; returns assistant message dict or None."""
    if not find_native_binary():
        return None
    tools_path: Path | None = None
    try:
        args = [
            "provider",
            "chat",
            "--base-url",
            base_url,
            "--model",
            model,
            "--timeout",
            str(timeout),
        ]
        if tools:
            tmp = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                delete=False,
                encoding="utf-8",
            )
            json.dump(tools, tmp, ensure_ascii=False)
            tmp.close()
            tools_path = Path(tmp.name)
            args.extend(["--tools", str(tools_path)])
        proc = _run_native(
            args,
            timeout=timeout + 30,
            input_text=json.dumps(messages, ensure_ascii=False),
        )
    finally:
        if tools_path and tools_path.is_file():
            tools_path.unlink(missing_ok=True)
    if proc is None or proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None
