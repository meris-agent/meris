"""Skills — on-demand knowledge loading (`.meris/skills/` + optional global)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from meris.harness.paths import harness_root

_SKILL_ICONS = {
    "plan": "📋",
    "harness": "⚙️",
    "security": "🔒",
    "debug": "🐛",
    "review": "🔍",
}


def _pkg_skills_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "templates" / "skills"


def global_skills_dir() -> Path:
    return Path.home() / ".meris" / "skills"


def parse_skill_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    block = text[4:end]
    meta: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip().lower()] = val.strip().strip("\"'")
    body = text[end + 5 :].lstrip("\n")
    return meta, body


def _title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip() or fallback
    return fallback


def _first_paragraph(body: str, max_len: int = 160) -> str:
    lines: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            if lines:
                break
            continue
        if line.startswith("#") or line.startswith("```"):
            if lines:
                break
            continue
        lines.append(line)
    text = " ".join(lines).strip()
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text or "按需通过 load_skill 加载"


def _guess_icon(name: str, meta: dict[str, str]) -> str:
    if meta.get("icon"):
        return meta["icon"]
    low = name.lower()
    for key, icon in _SKILL_ICONS.items():
        if key in low:
            return icon
    return "📋"


def skill_metadata(text: str, name: str) -> dict[str, str]:
    meta, body = parse_skill_frontmatter(text)
    title = meta.get("name") or meta.get("title") or _title_from_body(body, name)
    description = meta.get("description") or _first_paragraph(body)
    return {
        "title": title,
        "description": description,
        "icon": _guess_icon(name, meta),
    }


def _skill_prefs(workspace: Path) -> dict[str, Any]:
    from meris.harness.ui_config import load_skill_prefs

    return load_skill_prefs(workspace)


def is_skill_enabled(workspace: Path, name: str) -> bool:
    disabled = set(_skill_prefs(workspace).get("disabled") or [])
    return name not in disabled


def _project_skill_names(workspace: Path) -> list[str]:
    d = harness_root(workspace) / "skills"
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.md"))


def list_global_skill_names() -> list[str]:
    d = global_skills_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.md"))


def list_skills(workspace: Path, *, include_disabled: bool = False) -> list[str]:
    project = set(_project_skill_names(workspace))
    names: set[str] = set(project)
    for name in list_global_skill_names():
        if name not in project:
            names.add(name)
    ordered = sorted(names)
    if include_disabled:
        return ordered
    return [n for n in ordered if is_skill_enabled(workspace, n)]


def load_skill_content(workspace: Path, name: str) -> str | None:
    p = harness_root(workspace) / "skills" / f"{name}.md"
    if p.is_file():
        return p.read_text(encoding="utf-8")
    gp = global_skills_dir() / f"{name}.md"
    if gp.is_file():
        return gp.read_text(encoding="utf-8")
    bundled = _pkg_skills_dir() / f"{name}.md"
    if bundled.is_file():
        return bundled.read_text(encoding="utf-8")
    return None


def list_bundled_skill_names() -> list[str]:
    d = _pkg_skills_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.md"))


def _skill_item(
    *,
    name: str,
    text: str,
    path: str,
    source: str,
    workspace: Path,
    readonly: bool,
    installed: bool,
) -> dict[str, Any]:
    meta = skill_metadata(text, name)
    return {
        "name": name,
        "title": meta["title"],
        "description": meta["description"],
        "icon": meta["icon"],
        "path": path,
        "source": source,
        "enabled": is_skill_enabled(workspace, name),
        "readonly": readonly,
        "installed": installed,
    }


def list_skill_catalog(workspace: Path) -> list[dict[str, Any]]:
    """Installed (project) + global + bundled templates for settings UI."""
    project_names = set(_project_skill_names(workspace))
    items: list[dict[str, Any]] = []

    workspace_dir = harness_root(workspace) / "skills"
    if workspace_dir.is_dir():
        for p in sorted(workspace_dir.glob("*.md")):
            name = p.stem
            items.append(
                _skill_item(
                    name=name,
                    text=p.read_text(encoding="utf-8"),
                    path=f".meris/skills/{name}.md",
                    source="installed",
                    workspace=workspace,
                    readonly=False,
                    installed=True,
                )
            )

    global_dir = global_skills_dir()
    if global_dir.is_dir():
        for p in sorted(global_dir.glob("*.md")):
            name = p.stem
            if name in project_names:
                continue
            items.append(
                _skill_item(
                    name=name,
                    text=p.read_text(encoding="utf-8"),
                    path=f"~/.meris/skills/{name}.md",
                    source="global",
                    workspace=workspace,
                    readonly=False,
                    installed=True,
                )
            )

    for name in list_bundled_skill_names():
        if name in project_names:
            continue
        bundled = _pkg_skills_dir() / f"{name}.md"
        text = bundled.read_text(encoding="utf-8")
        meta = skill_metadata(text, name)
        items.append(
            {
                "name": name,
                "title": meta["title"],
                "description": meta["description"],
                "icon": meta["icon"],
                "path": f"templates/skills/{name}.md",
                "source": "builtin",
                "enabled": True,
                "readonly": True,
                "installed": False,
            }
        )

    return items


def skills_index(workspace: Path) -> str:
    names = list_skills(workspace)
    if not names:
        return "(no skills in .meris/skills/ or ~/.meris/skills/)"
    return "Available skills (use load_skill): " + ", ".join(names)
