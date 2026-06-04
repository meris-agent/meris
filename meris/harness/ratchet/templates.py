"""Shipped harness seeds for ratchet apply/create."""

from __future__ import annotations

from pathlib import Path

_PKG_TEMPLATES = Path(__file__).resolve().parent.parent.parent.parent / "templates"

# workspace-relative target → templates relative path
SEED_MAP: dict[str, str] = {
    ".meris/skills/plan-format.md": "skills/plan-format.md",
    ".meris/rules/paths.md": "rules/paths.md",
    ".meris/rules/workspace.md": "rules/workspace.md",
    ".meris/rules/project.md": "rules/project.md",
}


def seed_content(rel_target: str) -> str | None:
    key = rel_target.replace("\\", "/")
    tpl_rel = SEED_MAP.get(key)
    if not tpl_rel:
        return None
    path = _PKG_TEMPLATES / tpl_rel
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return None
