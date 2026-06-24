"""Path and content guardrails (100% enforcement)."""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath
from typing import Any


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def check_blocked_path(path: str, patterns: list[str]) -> str | None:
    """Return error if path matches a blocked glob."""
    norm = _norm(path)
    for pat in patterns:
        g = _norm(pat)
        if fnmatch.fnmatch(norm, g) or fnmatch.fnmatch(f"**/{norm}", g):
            return f"BLOCKED: path matches blocked pattern `{pat}`"
        # simple segment check
        parts = PurePosixPath(norm).parts
        for part in parts:
            if fnmatch.fnmatch(part, g.strip("*/")):
                return f"BLOCKED: path matches blocked pattern `{pat}`"
    return None


def check_tool_guardrails(
    tool: str,
    args: dict[str, Any],
    *,
    blocked_paths: list[str],
) -> str | None:
    if tool in ("write_file", "edit_file"):
        path = args.get("path", "")
        return check_blocked_path(path, blocked_paths)
    return None
