"""Git summary and ship helpers for Agent Window UI."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

_STATUS_LABELS = {
    "M": "modified",
    "A": "added",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "U": "updated",
    "?": "untracked",
    "!": "ignored",
}


def _run_git(cwd: Path, *args: str, timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode or 0, out.strip()


def is_git_repo(path: Path) -> bool:
    root = path.expanduser().resolve()
    if not root.is_dir():
        return False
    code, _ = _run_git(root, "rev-parse", "--git-dir")
    return code == 0


def _parse_branch_line(line: str) -> tuple[str, int, int]:
    """Parse `## branch...origin/main [ahead 1, behind 2]`."""
    branch = "HEAD"
    ahead = behind = 0
    if not line.startswith("## "):
        return branch, ahead, behind
    body = line[3:].strip()
    name_part = body.split("...")[0].strip()
    if name_part:
        branch = name_part
    m = re.search(r"ahead (\d+)", body)
    if m:
        ahead = int(m.group(1))
    m = re.search(r"behind (\d+)", body)
    if m:
        behind = int(m.group(1))
    return branch, ahead, behind


def _parse_porcelain_line(line: str) -> dict[str, Any] | None:
    if not line or line.startswith("##"):
        return None
    if len(line) < 3:
        return None
    x, y = line[0], line[1]
    path = line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    staged = x not in (" ", "?", "!")
    unstaged = y not in (" ", "?", "!")
    code = x if x not in (" ", "?") else y
    return {
        "path": path.replace("\\", "/"),
        "status": code,
        "label": _STATUS_LABELS.get(code, code),
        "staged": staged,
        "unstaged": unstaged,
    }


def git_summary(root: Path) -> dict[str, Any]:
    """Summary for one project root."""
    resolved = root.expanduser().resolve()
    base: dict[str, Any] = {
        "path": str(resolved),
        "name": resolved.name,
        "isRepo": False,
        "branch": "",
        "dirty": False,
        "stagedCount": 0,
        "unstagedCount": 0,
        "ahead": 0,
        "behind": 0,
        "files": [],
        "error": "",
    }
    if not resolved.is_dir():
        base["error"] = "not a directory"
        return base
    if not is_git_repo(resolved):
        base["error"] = "not a git repository"
        return base

    code, out = _run_git(resolved, "status", "--porcelain", "-b", "-u")
    if code != 0:
        base["error"] = out or "git status failed"
        return base

    branch = "HEAD"
    ahead = behind = 0
    files: list[dict[str, Any]] = []
    for line in out.splitlines():
        if line.startswith("##"):
            branch, ahead, behind = _parse_branch_line(line)
            continue
        ent = _parse_porcelain_line(line)
        if ent:
            files.append(ent)

    staged_count = sum(1 for f in files if f.get("staged"))
    unstaged_count = sum(1 for f in files if f.get("unstaged"))

    base.update(
        {
            "isRepo": True,
            "branch": branch,
            "dirty": bool(files),
            "stagedCount": staged_count,
            "unstagedCount": unstaged_count,
            "ahead": ahead,
            "behind": behind,
            "files": files[:80],
        }
    )
    return base


def git_summary_for_roots(roots: list[Path]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for root in roots:
        try:
            key = str(root.expanduser().resolve())
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(git_summary(Path(key)))
    return out


def git_stage_all(root: Path) -> dict[str, Any]:
    resolved = root.expanduser().resolve()
    if not is_git_repo(resolved):
        return {"ok": False, "error": "not a git repository"}
    code, out = _run_git(resolved, "add", "-A")
    if code != 0:
        return {"ok": False, "error": out or "git add failed"}
    summary = git_summary(resolved)
    return {"ok": True, "message": "已暂存全部改动", "summary": summary}


def git_commit(root: Path, message: str) -> dict[str, Any]:
    resolved = root.expanduser().resolve()
    msg = (message or "").strip()
    if not msg:
        return {"ok": False, "error": "commit message required"}
    if not is_git_repo(resolved):
        return {"ok": False, "error": "not a git repository"}
    summary_before = git_summary(resolved)
    if summary_before.get("stagedCount", 0) == 0:
        return {"ok": False, "error": "nothing staged — click Stage first"}
    code, out = _run_git(resolved, "commit", "-m", msg)
    if code != 0:
        return {"ok": False, "error": out or "git commit failed"}
    summary = git_summary(resolved)
    return {
        "ok": True,
        "message": out or "committed",
        "commitMessage": msg,
        "summary": summary,
    }


def suggest_commit_message(root: Path) -> str:
    """Heuristic message from staged (or unstaged) paths — no LLM."""
    resolved = root.expanduser().resolve()
    summary = git_summary(resolved)
    if not summary.get("isRepo"):
        return "chore: update project"
    files = [f for f in summary.get("files", []) if f.get("staged")]
    if not files:
        files = list(summary.get("files", []))
    if not files:
        return "chore: update project"

    paths = [str(f.get("path") or "") for f in files[:12]]
    tests = sum(1 for p in paths if "test" in p.lower())
    docs = sum(1 for p in paths if p.endswith(".md") or "/docs/" in p)
    if tests and not docs:
        prefix = "test"
    elif docs and len(paths) <= 2:
        prefix = "docs"
    elif len(paths) == 1:
        prefix = "fix" if any(x in paths[0] for x in ("fix", "bug")) else "feat"
    else:
        prefix = "feat"
    if len(paths) == 1:
        tail = Path(paths[0]).stem
        return f"{prefix}: update {tail}"
    return f"{prefix}: update {len(paths)} files"
