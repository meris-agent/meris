"""Harness — State subsystem (PROGRESS.md)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

PROGRESS_FILE = "PROGRESS.md"
RATCHET_SUMMARY_HEADER = "## Ratchet 摘要"
MAX_PROGRESS_PROMPT = 8000
MAX_SESSION_NOTES = 3


def load_progress(workspace: Path) -> str:
    p = workspace / PROGRESS_FILE
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return ""


def load_progress_for_prompt(workspace: Path, *, max_chars: int = MAX_PROGRESS_PROMPT) -> str:
    """Prefer Ratchet summary + recent session notes; avoid dumping full PROGRESS."""
    text = load_progress(workspace)
    if not text:
        return ""

    parts: list[str] = []

    m = re.search(
        rf"^{re.escape(RATCHET_SUMMARY_HEADER)}.*?(?=^## |\Z)",
        text,
        re.M | re.S,
    )
    if m:
        parts.append(m.group(0).strip())

    notes = re.findall(
        r"^## Session note \([^)]+\)\n.*?(?=^## |\Z)",
        text,
        re.M | re.S,
    )
    for block in notes[-MAX_SESSION_NOTES:]:
        parts.append(block.strip())

    if not parts:
        return text[:max_chars]

    joined = "\n\n".join(parts)
    return joined[:max_chars]


def append_progress_note(workspace: Path, note: str) -> None:
    p = workspace / PROGRESS_FILE
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = f"\n\n## Session note ({ts})\n"
    if p.is_file():
        p.write_text(p.read_text(encoding="utf-8") + header + note, encoding="utf-8")
    else:
        p.write_text(f"# Project progress\n{header}{note}", encoding="utf-8")


def append_ratchet_summary_line(workspace: Path, line: str) -> None:
    """Add one bullet under Ratchet summary (create section if missing)."""
    p = workspace / PROGRESS_FILE
    bullet = f"- {line.strip()}\n"
    if not p.is_file():
        p.write_text(f"# Project progress\n\n{RATCHET_SUMMARY_HEADER}\n\n{bullet}", encoding="utf-8")
        return

    text = p.read_text(encoding="utf-8")
    if RATCHET_SUMMARY_HEADER not in text:
        text = text.rstrip() + f"\n\n{RATCHET_SUMMARY_HEADER}\n\n{bullet}"
        p.write_text(text, encoding="utf-8")
        return

    if bullet.strip() in text:
        return

    m = re.search(rf"^({re.escape(RATCHET_SUMMARY_HEADER)}.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        text = text.rstrip() + f"\n\n{RATCHET_SUMMARY_HEADER}\n\n{bullet}"
    else:
        block = m.group(1).rstrip() + "\n" + bullet
        text = text[: m.start()] + block + text[m.end() :]
    p.write_text(text, encoding="utf-8")


def update_progress_task(workspace: Path, task: str, status: str = "completed") -> None:
    """Record task outcome at end of session."""
    append_progress_note(workspace, f"- **Task**: {task}\n- **Status**: {status}\n")
