"""Load PreToolUse / PostToolUse hooks from .meris/settings.json."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from meris.harness.hooks import HookResult, HookRunner


def _matches(matcher: str | None, tool: str) -> bool:
    if not matcher:
        return True
    if "|" in matcher and not any(c in matcher for c in ".*+?[]()"):
        return tool in matcher.split("|")
    try:
        return bool(re.search(matcher, tool))
    except re.error:
        return tool == matcher


async def _run_hook_command(workspace: Path, command: str, env: dict[str, str]) -> HookResult:
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=workspace,
        env={**os.environ, **env},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        return HookResult(block=True, message="hook timed out after 120s")
    text = out.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        return HookResult(block=True, message=text or f"hook exited {proc.returncode}")
    return HookResult(block=False, message=text)


def _make_pre_hook(
    workspace: Path,
    command: str,
    matcher: str | None,
) -> Any:
    async def pre_fn(tool: str, args: dict[str, Any]) -> HookResult:
        if not _matches(matcher, tool):
            return HookResult()
        env = {
            "MERIS_TOOL_NAME": tool,
            "MERIS_TOOL_ARGS": json.dumps(args, ensure_ascii=False),
            "MERIS_HOOK_PHASE": "pre",
        }
        return await _run_hook_command(workspace, command, env)

    return pre_fn


def _make_post_hook(
    workspace: Path,
    command: str,
    matcher: str | None,
) -> Any:
    async def post_fn(tool: str, args: dict[str, Any], result: str) -> HookResult:
        if not _matches(matcher, tool):
            return HookResult()
        env = {
            "MERIS_TOOL_NAME": tool,
            "MERIS_TOOL_ARGS": json.dumps(args, ensure_ascii=False),
            "MERIS_TOOL_RESULT": result[:8000],
            "MERIS_HOOK_PHASE": "post",
        }
        return await _run_hook_command(workspace, command, env)

    return post_fn


def build_hook_runner(workspace: Path, settings: dict) -> HookRunner:
    """Build HookRunner from settings.hooks (shell hooks on tool use)."""
    runner = HookRunner()
    hooks_cfg = settings.get("hooks") or {}

    for entry in hooks_cfg.get("preToolUse") or []:
        if isinstance(entry, str):
            runner.on_pre(_make_pre_hook(workspace, entry, None))
        elif isinstance(entry, dict) and entry.get("command"):
            runner.on_pre(
                _make_pre_hook(workspace, entry["command"], entry.get("matcher"))
            )

    for entry in hooks_cfg.get("postToolUse") or []:
        if isinstance(entry, str):
            runner.on_post(_make_post_hook(workspace, entry, None))
        elif isinstance(entry, dict) and entry.get("command"):
            runner.on_post(
                _make_post_hook(workspace, entry["command"], entry.get("matcher"))
            )

    return runner
