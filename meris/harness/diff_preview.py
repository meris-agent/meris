"""Build inline diff preview for file_change events (Phase H5)."""

from __future__ import annotations

from typing import Any

_MAX_LINES = 20
_MAX_CHARS = 2400


def _truncate(text: str, limit: int = _MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n… (truncated)"


def build_file_change_preview(tool: str, args: dict[str, Any]) -> str:
    """Unified-style preview for write_file / edit_file tool args."""
    path = str(args.get("path") or "")
    if not path:
        return ""

    if tool == "write_file":
        content = str(args.get("content") or "")
        lines = content.splitlines()
        body: list[str] = [f"--- /dev/null", f"+++ {path}", "@@ new file @@"]
        for line in lines[:_MAX_LINES]:
            body.append(f"+{line}")
        if len(lines) > _MAX_LINES:
            body.append(f"… ({len(lines) - _MAX_LINES} more lines)")
        return _truncate("\n".join(body))

    if tool == "edit_file":
        old = str(args.get("old_string") or "")
        new = str(args.get("new_string") or "")
        body = [f"--- {path}", f"+++ {path}", "@@ edit @@"]
        for line in old.splitlines()[:_MAX_LINES]:
            body.append(f"-{line}")
        for line in new.splitlines()[:_MAX_LINES]:
            body.append(f"+{line}")
        return _truncate("\n".join(body))

    return ""
