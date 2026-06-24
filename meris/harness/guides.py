"""Harness — Guides subsystem (AGENTS.md, CLAUDE.md)."""

from __future__ import annotations

from pathlib import Path

from meris.harness.paths import harness_root
from meris.harness.ratchet.profile import load_profile_text
from meris.harness.skills import skills_index

GUIDE_FILES = ("AGENTS.md", "CLAUDE.md")
RULE_BODY_MAX = 4000
RULE_INDEX_HINT = "read_file `.meris/rules/{name}` when the task touches this topic"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
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


def _rule_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip() or fallback
    return fallback


def load_guides(workspace: Path, max_chars: int = 12_000) -> str:
    parts: list[str] = []
    for name in GUIDE_FILES:
        p = workspace / name
        if p.is_file():
            parts.append(f"<!-- {name} -->\n{p.read_text(encoding='utf-8')[:max_chars]}")
    hroot = harness_root(workspace)
    extra = hroot / "AGENTS.md"
    if extra.is_file():
        parts.append(
            f"<!-- {hroot.name}/AGENTS.md -->\n{extra.read_text(encoding='utf-8')[:max_chars]}"
        )
    rules_dir = hroot / "rules"
    index_lines: list[str] = []
    if rules_dir.is_dir():
        for rp in sorted(rules_dir.glob("*.md")):
            raw = rp.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(raw)
            inject = meta.get("inject", "on-demand").lower()
            rel = f"{hroot.name}/rules/{rp.name}"
            if inject == "always":
                parts.append(f"<!-- {rel} -->\n{body[:RULE_BODY_MAX]}")
            else:
                title = _rule_title(body, rp.stem)
                index_lines.append(
                    f"- **{rp.name}** — {title} (`{RULE_INDEX_HINT.format(name=rp.name)}`)"
                )
        if index_lines:
            parts.append(
                "<!-- rules index -->\n## Rules (load on demand)\n" + "\n".join(index_lines)
            )
    return "\n\n".join(parts)


def estimate_prompt_chars(workspace: Path, mode: str = "run") -> int:
    return len(build_system_prompt(workspace, mode=mode))


def build_system_prompt(workspace: Path, mode: str = "run") -> str:
    guides = load_guides(workspace)
    base = """You are Meris, a harness-first coding agent. Follow project guides strictly.
Use tools to inspect before editing. Prefer edit_file over write_file for small changes.
When done, summarize changes and suggest verification commands.
Python package and source paths use the `meris/` directory (e.g. meris/cli.py, meris/harness/).
Deep docs live under docs/harness/ — read_file when AGENTS.md points there."""

    if mode == "ask":
        base += "\n\nMODE: ASK — read-only. Do not call write_file, edit_file, or bash that mutates state."
    elif mode == "review":
        base += (
            "\n\nMODE: REVIEW — read-only code review. Do not call write_file, edit_file, bash, or git_commit."
            "\nOutput markdown: ## Summary, ## Issues (`- [ ]` checklist), ## Suggestions."
        )
    elif mode == "plan":
        base += (
            "\n\nMODE: PLAN — produce a markdown task list only. Do not modify source files."
            "\nRequired format: one task per line as `- [ ] description` (space inside brackets)."
            "\nInclude at least 3 `- [ ]` lines unless the user specifies another count."
            "\nDo not use numbered lists instead of checkboxes."
            "\nReference files as `meris/...` (e.g. meris/cli.py). End with a short summary."
            "\nFull rules: docs/harness/plan-format.md"
        )

    if guides:
        base = f"{base}\n\n# Project guides\n\n{guides}"
    from meris.harness.handoff import load_handoff_for_prompt

    handoff = load_handoff_for_prompt(workspace)
    if handoff:
        base = (
            f"{base}\n\n# Prior session handoff (continue from here if task was interrupted)\n\n"
            f"{handoff}"
        )
    from meris.harness.environment import load_environment_for_prompt

    env_block = load_environment_for_prompt(workspace)
    if env_block:
        base = f"{base}\n\n# Environment contract\n\n{env_block}"
    profile = load_profile_text(workspace)
    if profile.strip():
        base = f"{base}\n\n# User profile\n\n{profile}"
    skill_idx = skills_index(workspace)
    if skill_idx:
        base = f"{base}\n\n# Skills\n\n{skill_idx}"
    return base
