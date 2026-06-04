"""Rule engine: events → proposals."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from meris.harness.paths import harness_root
from meris.harness.ratchet.proposal import Proposal, ProposalTarget, new_proposal_id

LESSON_TARGETS: dict[str, str] = {
    "L-format": ".meris/skills/plan-format.md",
    "L-cwd": ".meris/rules/workspace.md",
    "L-path": ".meris/rules/paths.md",
}


def _detail(ev: dict[str, Any]) -> str:
    return (ev.get("detail") or "").lower()


def _lesson_applied(workspace: Path, lesson: str, proposals: list[Proposal]) -> bool:
    for p in proposals:
        if p.lesson == lesson and p.status == "pending":
            return True
    rel = LESSON_TARGETS.get(lesson)
    if rel:
        fp = workspace / rel
        if fp.is_file() and f"ratchet:{lesson}" in fp.read_text(encoding="utf-8"):
            return True
    hroot = harness_root(workspace)
    for rp in (hroot / "rules").glob("*.md") if (hroot / "rules").is_dir() else []:
        if f"ratchet:{lesson}" in rp.read_text(encoding="utf-8"):
            return True
    for sp in (hroot / "skills").glob("*.md") if (hroot / "skills").is_dir() else []:
        if f"ratchet:{lesson}" in sp.read_text(encoding="utf-8"):
            return True
    return False


def _plan_format_proposal(ev: dict[str, Any]) -> Proposal:
    marker = "<!-- ratchet:L-format -->"
    content = f"""{marker}

## Ratchet (auto)

- Plan / benchmark 输出必须包含 `- [ ]`（中括号内有空格），至少 3 条。
- 触发: {ev.get("kind")} {ev.get("task_id", "")}
"""
    return Proposal(
        id=new_proposal_id(),
        lesson="L-format",
        summary="Plan 输出缺少 `- [ ]` checkbox 格式",
        target=ProposalTarget(
            path=".meris/skills/plan-format.md",
            action="create",
            content=content,
        ),
        signals=[f"{ev.get('kind')}:{ev.get('task_id', '')}"],
        verify=["meris benchmark run --filter plan_smoke"],
    )


def _workspace_proposal(ev: dict[str, Any]) -> Proposal:
    marker = "<!-- ratchet:L-cwd -->"
    content = f"""{marker}

## Ratchet (auto)

- 改代码 / README / pytest 时 cwd 必须是 **本项目 git 仓库根**，不要在父目录跑 agent 改子目录 README。
- 触发: {ev.get("detail", "")[:120]}
"""
    return Proposal(
        id=new_proposal_id(),
        lesson="L-cwd",
        summary="工作区 cwd 错误导致路径被 block",
        target=ProposalTarget(
            path=".meris/rules/workspace.md",
            action="create",
            content=content,
        ),
        signals=[ev.get("kind", "")],
        verify=[],
    )


def _paths_proposal(ev: dict[str, Any]) -> Proposal:
    marker = "<!-- ratchet:L-path -->"
    content = f"""{marker}

## Ratchet (auto)

- 仓库根文档用 `README.md`，不要写成 `meris/README.md`（除非 cwd 在父目录且项目是子文件夹）。
- 不要使用已废弃的 `forge/` 路径前缀。
"""
    return Proposal(
        id=new_proposal_id(),
        lesson="L-path",
        summary="路径/命名不规范（meris/README、forge/ 等）",
        target=ProposalTarget(
            path=".meris/rules/paths.md",
            action="create",
            content=content,
        ),
        signals=[ev.get("kind", "")],
        verify=[],
    )


def classify_event(
    workspace: Path,
    ev: dict[str, Any],
    existing: list[Proposal],
) -> Proposal | None:
    kind = ev.get("kind", "")
    det = _detail(ev)
    task = (ev.get("task") or "").lower()

    if kind == "benchmark_fail" and "missing: [ ]" in det:
        if not _lesson_applied(workspace, "L-format", existing):
            return _plan_format_proposal(ev)

    if kind in ("benchmark_fail", "permission_denied", "approve_denied"):
        if "block" in det or "denied" in det or "permission" in det or "blocked" in det:
            if "readme" in det or "meris/" in det or "blockedpaths" in det.replace(" ", ""):
                if not _lesson_applied(workspace, "L-cwd", existing):
                    return _workspace_proposal(ev)

    if kind == "benchmark_fail" and ("meris/readme" in det or "forge/" in det):
        if not _lesson_applied(workspace, "L-path", existing):
            return _paths_proposal(ev)

    if "forge/" in task or "meris/readme" in task:
        if not _lesson_applied(workspace, "L-path", existing):
            return _paths_proposal(ev)

    return None


def classify_events(workspace: Path, events: list[dict[str, Any]]) -> list[Proposal]:
    created: list[Proposal] = []
    for ev in events:
        p = classify_event(workspace, ev, created)
        if p:
            created.append(p)
    return created
