"""Code review helper — git diff → read-only agent task (Phase E5)."""

from __future__ import annotations

import subprocess
from pathlib import Path

_MAX_DIFF = 14_000


def git_diff(workspace: Path, *, staged: bool = False) -> str:
    ws = workspace.resolve()
    cmd = ["git", "diff", "--cached"] if staged else ["git", "diff"]
    proc = subprocess.run(
        cmd,
        cwd=ws,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode not in (0, 1):
        err = (proc.stderr or proc.stdout or "git diff failed").strip()
        raise RuntimeError(err)
    return proc.stdout or ""


def build_review_task(workspace: Path, *, staged: bool = False) -> str:
    diff = git_diff(workspace, staged=staged).strip()
    return build_review_task_from_diff(diff, staged=staged)


def build_review_task_from_diff(diff: str, *, staged: bool = False) -> str:
    diff = diff.strip()
    if not diff:
        scope = "staged" if staged else "working tree"
        raise RuntimeError(f"No diff in {scope} — stage changes or edit files first")
    if len(diff) > _MAX_DIFF:
        diff = diff[:_MAX_DIFF] + "\n\n... (diff truncated)\n"
    label = "staged" if staged else "unstaged"
    return f"""Review the following {label} git diff. **Do not modify files.**

Output markdown with these sections:
## Summary
## Issues
Use `- [ ]` checklist items (one issue per line).
## Suggestions

```diff
{diff}
```"""
