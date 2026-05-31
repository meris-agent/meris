"""Harness — State subsystem (PROGRESS.md)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

PROGRESS_FILE = "PROGRESS.md"


def load_progress(workspace: Path) -> str:
    p = workspace / PROGRESS_FILE
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return ""


def append_progress_note(workspace: Path, note: str) -> None:
    p = workspace / PROGRESS_FILE
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = f"\n\n## Session note ({ts})\n"
    if p.is_file():
        p.write_text(p.read_text(encoding="utf-8") + header + note, encoding="utf-8")
    else:
        p.write_text(f"# Project progress\n{header}{note}", encoding="utf-8")


def update_progress_task(workspace: Path, task: str, status: str = "completed") -> None:
    """Record task outcome at end of session."""
    append_progress_note(workspace, f"- **Task**: {task}\n- **Status**: {status}\n")
