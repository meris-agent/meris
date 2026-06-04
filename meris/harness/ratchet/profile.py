"""User habit profile from ratchet events."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from meris.harness.paths import harness_root
from meris.harness.ratchet.events import load_events

PROFILE_NAME = "profile.md"
MAX_PROFILE_LINES = 40


def profile_path(workspace: Path) -> Path:
    return harness_root(workspace) / PROFILE_NAME


def load_profile_text(workspace: Path, *, max_chars: int = 2000) -> str:
    p = profile_path(workspace)
    if p.is_file():
        return p.read_text(encoding="utf-8")[:max_chars]
    return ""


def rebuild_profile(workspace: Path, *, since_days: int = 30) -> Path | None:
    """Regenerate `.meris/profile.md` from approve_denied / permission events."""
    ws = workspace.resolve()
    events = load_events(ws, since_days=since_days)

    deny_tools: Counter[str] = Counter()
    deny_cmds: Counter[str] = Counter()
    approve_denies = 0
    perm_blocks = 0

    for ev in events:
        kind = ev.get("kind", "")
        tool = ev.get("tool", "")
        if kind == "approve_denied":
            approve_denies += 1
            if tool:
                deny_tools[tool] += 1
            summary = ev.get("args_summary", "")
            if "git push" in summary:
                deny_cmds["git push"] += 1
            if "rm " in summary or "rm-" in summary:
                deny_cmds["destructive rm"] += 1
        elif kind == "permission_denied":
            perm_blocks += 1

    if not approve_denies and not perm_blocks:
        return None

    lines = [
        "# User profile (Ratchet)",
        "",
        "> 由 `.meris/ratchet/events.jsonl` 自动归纳，可手改。",
        "",
    ]
    if approve_denies:
        lines.append(f"- 使用 `--approve` 时曾拒绝 **{approve_denies}** 次工具调用")
        top = deny_tools.most_common(4)
        if top:
            lines.append("- 常拒绝工具：" + ", ".join(f"`{t}`×{n}" for t, n in top))
        if deny_cmds:
            lines.append(
                "- 常拒绝操作："
                + ", ".join(f"`{c}`×{n}" for c, n in deny_cmds.most_common(3))
            )
        lines.append("- 倾向：改源码 / 写文件前优先征得确认")
    if perm_blocks:
        lines.append(f"- 权限拦截记录 **{perm_blocks}** 次 — 检查 cwd 与 `.meris/settings.json` blockedPaths")

    text = "\n".join(lines[:MAX_PROFILE_LINES]) + "\n"
    dest = profile_path(ws)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest
