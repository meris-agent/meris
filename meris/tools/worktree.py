"""Git worktree isolation for parallel run sessions."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from pathlib import Path

from meris.harness.paths import harness_root


@dataclass
class WorktreeInfo:
    path: Path
    branch: str


async def _git(workspace: Path, *args: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=workspace,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
    return proc.returncode or 0, out.decode("utf-8", errors="replace")


async def is_git_repo(workspace: Path) -> bool:
    code, _ = await _git(workspace, "rev-parse", "--git-dir")
    return code == 0


async def create_worktree(workspace: Path, label: str | None = None) -> WorktreeInfo:
    """Create an isolated worktree under .meris/worktrees/."""
    ws = workspace.resolve()
    if not await is_git_repo(ws):
        raise RuntimeError("workspace is not a git repository")
    tag = label or uuid.uuid4().hex[:8]
    branch = f"meris/session-{tag}"
    wt_path = harness_root(ws) / "worktrees" / tag
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    code, out = await _git(ws, "worktree", "add", "-b", branch, str(wt_path))
    if code != 0:
        raise RuntimeError(f"git worktree add failed: {out}")
    return WorktreeInfo(path=wt_path, branch=branch)


async def remove_worktree(workspace: Path, info: WorktreeInfo) -> None:
    ws = workspace.resolve()
    await _git(ws, "worktree", "remove", "--force", str(info.path))
    await _git(ws, "branch", "-D", info.branch)
