"""Harness — Guides subsystem (AGENTS.md, CLAUDE.md)."""

from __future__ import annotations

from pathlib import Path

from meris.harness.paths import harness_root
from meris.harness.skills import skills_index

GUIDE_FILES = ("AGENTS.md", "CLAUDE.md")


def load_guides(workspace: Path, max_chars: int = 12_000) -> str:
    parts: list[str] = []
    for name in GUIDE_FILES:
        p = workspace / name
        if p.is_file():
            parts.append(f"<!-- {name} -->\n{p.read_text(encoding='utf-8')[:max_chars]}")
    hroot = harness_root(workspace)
    extra = hroot / "AGENTS.md"
    if extra.is_file():
        parts.append(f"<!-- {hroot.name}/AGENTS.md -->\n{extra.read_text(encoding='utf-8')[:max_chars]}")
    rules_dir = hroot / "rules"
    if rules_dir.is_dir():
        for rp in sorted(rules_dir.glob("*.md")):
            parts.append(
                f"<!-- {hroot.name}/rules/{rp.name} -->\n{rp.read_text(encoding='utf-8')[:4000]}"
            )
    return "\n\n".join(parts)


def build_system_prompt(workspace: Path, mode: str = "run") -> str:
    guides = load_guides(workspace)
    base = """You are Meris, a harness-first coding agent. Follow project guides strictly.
Use tools to inspect before editing. Prefer edit_file over write_file for small changes.
When done, summarize changes and suggest verification commands."""

    if mode == "ask":
        base += "\n\nMODE: ASK — read-only. Do not call write_file, edit_file, or bash that mutates state."
    elif mode == "plan":
        base += (
            "\n\nMODE: PLAN — produce a markdown task list only. Do not modify files."
            "\nUse checkbox items (- [ ] task). End with a short summary."
        )

    if guides:
        base = f"{base}\n\n# Project guides\n\n{guides}"
    skill_idx = skills_index(workspace)
    if skill_idx:
        base = f"{base}\n\n# Skills\n\n{skill_idx}"
    return base
