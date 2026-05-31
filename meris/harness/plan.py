"""Plan mode output — persist task lists to disk."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from meris.harness.paths import harness_root

DEFAULT_PLAN_FILE = "plan/tasks.md"


def default_plan_path(workspace: Path) -> Path:
    return harness_root(workspace) / "plan" / "tasks.md"


def resolve_plan_path(workspace: Path, out: str | Path | None = None) -> Path:
    if out is None:
        return default_plan_path(workspace)
    p = Path(out)
    if not p.is_absolute():
        p = workspace / p
    return p


def save_plan(workspace: Path, content: str, out: str | Path | None = None) -> Path:
    """Write plan markdown with header timestamp."""
    path = resolve_plan_path(workspace, out)
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = content.strip()
    if not body.startswith("#"):
        body = f"# Task plan ({ts})\n\n{body}"
    path.write_text(body + "\n", encoding="utf-8")
    return path


def extract_last_assistant_text(messages: list[dict]) -> str | None:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            text = (msg.get("content") or "").strip()
            if text:
                return text
    return None
