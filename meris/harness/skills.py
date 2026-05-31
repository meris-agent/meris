"""Skills — on-demand knowledge loading (`.meris/skills/`)."""

from __future__ import annotations

from pathlib import Path

from meris.harness.paths import harness_root


def list_skills(workspace: Path) -> list[str]:
    d = harness_root(workspace) / "skills"
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.md"))


def load_skill_content(workspace: Path, name: str) -> str | None:
    p = harness_root(workspace) / "skills" / f"{name}.md"
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8")


def skills_index(workspace: Path) -> str:
    names = list_skills(workspace)
    if not names:
        return "(no skills in .meris/skills/)"
    return "Available skills (use load_skill): " + ", ".join(names)
