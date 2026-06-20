"""Plan mode output — persist task lists to disk."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from meris.harness.paths import harness_root

DEFAULT_PLAN_FILE = "plan/tasks.md"
_CHECKBOX_RE = re.compile(r"^(\s*-\s+\[)( |x|X)(\]\s+)(.+)$")


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


def apply_plan_checkbox_updates(text: str, items: list[dict]) -> str:
    """Update `- [ ]` lines by index; preserve headers and non-checkbox prose."""
    if not items:
        return text
    lines = text.splitlines()
    checkbox_indices: list[int] = []
    for i, line in enumerate(lines):
        if _CHECKBOX_RE.match(line):
            checkbox_indices.append(i)

    for j, item in enumerate(items):
        if j >= len(checkbox_indices):
            break
        idx = checkbox_indices[j]
        line = lines[idx]
        m = _CHECKBOX_RE.match(line)
        if not m:
            continue
        mark = "x" if item.get("done") else " "
        task_text = (item.get("text") or m.group(4)).strip()
        lines[idx] = f"{m.group(1)}{mark}{m.group(3)}{task_text}"

    body = "\n".join(lines)
    if text.endswith("\n"):
        body += "\n"
    return body


def mark_plan_items_done(workspace: Path, out: str | Path, texts: list[str]) -> Path | None:
    """Mark plan checkbox lines done when task text matches (Plan → Run sync)."""
    if not texts:
        return None
    path = resolve_plan_path(workspace, out)
    if not path.is_file():
        return None
    want = {t.strip() for t in texts if t.strip()}
    items = parse_plan_checkboxes(path.read_text(encoding="utf-8"))
    if not items:
        return None
    changed = False
    for item in items:
        if item["text"] in want and not item.get("done"):
            item["done"] = True
            changed = True
    if not changed:
        return path
    return sync_plan_items(workspace, out, items)


def sync_plan_items(workspace: Path, out: str | Path, items: list[dict]) -> Path:
    """Merge checkbox states into an existing plan file (or create a minimal one)."""
    path = resolve_plan_path(workspace, out)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        body = apply_plan_checkbox_updates(text, items)
    else:
        body = "# Task plan\n\n" + "\n".join(
            f"- [{'x' if i.get('done') else ' '}] {i.get('text', '')}" for i in items
        )
        if not body.endswith("\n"):
            body += "\n"
    path.write_text(body, encoding="utf-8")
    return path


def extract_last_assistant_text(messages: list[dict]) -> str | None:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            text = (msg.get("content") or "").strip()
            if text:
                return text
    return None


def parse_plan_checkboxes(text: str) -> list[dict]:
    """Parse `- [ ]` / `- [x]` lines for Plan UI (Phase I4)."""
    items: list[dict] = []
    for line in text.splitlines():
        m = re.match(r"^-\s+\[( |x|X)\]\s+(.+)$", line.strip())
        if m:
            items.append({"done": m.group(1).lower() == "x", "text": m.group(2).strip()})
    return items
