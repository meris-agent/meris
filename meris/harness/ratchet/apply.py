"""Apply ratchet proposals to harness files."""

from __future__ import annotations

import shutil
from pathlib import Path

from meris.harness.memory import append_ratchet_summary_line
from meris.harness.ratchet.paths import applied_dir
from meris.harness.ratchet.proposal import Proposal, delete_pending_proposal, save_proposal
from meris.harness.ratchet.templates import seed_content

ALLOWED_PREFIXES = (
    ".meris/rules/",
    ".meris/skills/",
)


def is_allowed_target(
    rel_path: str,
    *,
    force_agents: bool = False,
    force_settings: bool = False,
) -> bool:
    norm = rel_path.replace("\\", "/")
    if norm == ".meris/profile.md":
        return True
    if force_settings and norm.startswith(".meris/settings"):
        return True
    if any(norm.startswith(p) for p in ALLOWED_PREFIXES):
        return True
    if force_agents and norm == "AGENTS.md":
        return True
    return False


def _write_target(ws: Path, dest: Path, proposal: Proposal) -> None:
    content = proposal.target.content
    marker = proposal.marker()
    rel = proposal.target.path.replace("\\", "/")
    action = proposal.target.action

    if action == "patch_section" and dest.is_file():
        text = dest.read_text(encoding="utf-8")
        if marker in text:
            return
        heading = content.strip().splitlines()[0] if content.strip() else "## Ratchet"
        body = content.strip()
        if body.startswith(heading):
            body = "\n".join(body.splitlines()[1:]).strip()
        block = f"{marker}\n\n{heading}\n\n{body}\n"
        sep = "\n" if text.endswith("\n") else "\n\n"
        dest.write_text(text + sep + block, encoding="utf-8")
        return

    if not dest.is_file():
        seed = seed_content(rel)
        base = (seed.rstrip() + "\n\n") if seed else ""
        dest.write_text(base + content.lstrip(), encoding="utf-8")
        return

    text = dest.read_text(encoding="utf-8")
    if marker in text:
        return
    sep = "\n" if text.endswith("\n") else "\n\n"
    dest.write_text(text + sep + content.lstrip(), encoding="utf-8")


def apply_proposal(
    workspace: Path,
    proposal: Proposal,
    *,
    force_agents: bool = False,
    force_settings: bool = False,
    update_progress: bool = True,
) -> Path:
    """Write proposal content; archive proposal under applied/."""
    ws = workspace.resolve()
    rel = proposal.target.path.replace("\\", "/")
    if not is_allowed_target(rel, force_agents=force_agents, force_settings=force_settings):
        raise ValueError(f"Target not allowed for auto-apply: {rel}")

    dest = ws / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    backup_root = applied_dir(ws) / proposal.id / "backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        shutil.copy2(dest, backup_root / dest.name)

    _write_target(ws, dest, proposal)

    proposal.status = "applied"
    delete_pending_proposal(ws, proposal.id)
    save_proposal(ws, proposal, applied=True)

    if update_progress:
        append_ratchet_summary_line(ws, f"[{proposal.lesson}] {proposal.summary}")

    return dest


def revert_proposal(workspace: Path, proposal_id: str) -> bool:
    """Restore files from applied backup."""
    ws = workspace.resolve()
    backup_root = applied_dir(ws) / proposal_id / "backup"
    if not backup_root.is_dir():
        return False
    from meris.harness.ratchet.proposal import load_proposal

    prop = load_proposal(ws, proposal_id)
    if not prop:
        return False
    for fp in backup_root.iterdir():
        if fp.is_file():
            dest = ws / prop.target.path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fp, dest)
    return True
