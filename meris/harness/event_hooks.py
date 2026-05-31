"""Event hooks — onSave / onCommit triggered after file or git operations."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from meris.harness.hooks import HookResult
from meris.harness.hooks_loader import _run_hook_command


def _path_matches(matcher: str | None, rel_path: str) -> bool:
    if not matcher:
        return True
    norm = rel_path.replace("\\", "/")
    if "|" in matcher and not any(c in matcher for c in ".*+?[]()"):
        return any(norm.endswith(p.strip()) or p.strip() in norm for p in matcher.split("|"))
    try:
        return bool(re.search(matcher, norm))
    except re.error:
        return fnmatch_simple(matcher, norm)


def fnmatch_simple(pattern: str, path: str) -> bool:
    import fnmatch

    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(PurePosixPath(path).name, pattern)


async def run_event_hooks(
    workspace: Path,
    settings: dict,
    event: str,
    *,
    path: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> list[HookResult]:
    """Run onSave / onCommit hooks from settings.hooks."""
    hooks_cfg = settings.get("hooks") or {}
    entries = hooks_cfg.get(event) or []
    if not entries:
        return []

    results: list[HookResult] = []
    for entry in entries:
        if isinstance(entry, str):
            cmd, matcher = entry, None
        elif isinstance(entry, dict):
            cmd = entry.get("command", "")
            matcher = entry.get("matcher")
        else:
            continue
        if not cmd:
            continue
        if path and matcher and not _path_matches(matcher, path):
            continue
        env = {
            "MERIS_EVENT": event,
            "MERIS_HOOK_PHASE": event,
            "MERIS_SAVED_PATH": path or "",
        }
        if extra_env:
            env.update(extra_env)
        results.append(await _run_hook_command(workspace, cmd, env))
    return results
