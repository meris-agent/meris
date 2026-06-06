"""Hook bridge for meris-rs native agent (P5-4 M4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from meris.harness.event_hooks import run_event_hooks
from meris.harness.hooks import HookResult
from meris.harness.hooks_loader import build_hook_runner
from meris.harness.settings import load_settings


async def run_pre_tool_hook(workspace: Path, tool: str, args: dict[str, Any]) -> HookResult:
    settings = load_settings(workspace)
    runner = build_hook_runner(workspace, settings)
    return await runner.run_pre(tool, args)


async def run_post_tool_hook(
    workspace: Path,
    tool: str,
    args: dict[str, Any],
    result: str,
) -> HookResult:
    settings = load_settings(workspace)
    runner = build_hook_runner(workspace, settings)
    return await runner.run_post(tool, args, result)


async def run_on_save_hooks(workspace: Path, rel_path: str) -> HookResult:
    settings = load_settings(workspace)
    results = await run_event_hooks(workspace, settings, "onSave", path=rel_path)
    for r in results:
        if r.block:
            return r
    messages = [r.message for r in results if r.message]
    return HookResult(block=False, message="\n".join(messages))


def hook_result_json(result: HookResult) -> str:
    return json.dumps({"block": result.block, "message": result.message})
