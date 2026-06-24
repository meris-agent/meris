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
    "L-harness-check": ".meris/rules/paths.md",
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
        verify=["meris harness check", "meris benchmark run --filter plan_smoke"],
        target_failure="Plan/benchmark output missing `- [ ]` checkbox lines",
        expected_effect="Plan mode outputs at least 3 `- [ ]` tasks",
        regression_risk="May add redundant plan-format bullets if already documented",
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
        target_failure="Wrong cwd — agent tried to edit child repo from parent workspace",
        expected_effect="Switch cwd to git repo root before code/README changes",
        regression_risk="Low — workspace rule only",
    )


def _paths_proposal(ev: dict[str, Any]) -> Proposal:
    marker = "<!-- ratchet:L-path -->"
    content = f"""{marker}

## Ratchet (auto)

- 仓库根文档用 `README.md`，不要写成 `meris/README.md`（除非 cwd 在父目录且项目是子文件夹）。
- 不要使用与本仓库布局不符的路径前缀（以 AGENTS.md 为准）。
"""
    return Proposal(
        id=new_proposal_id(),
        lesson="L-path",
        summary="路径/命名不规范（meris/README、错误包目录前缀等）",
        target=ProposalTarget(
            path=".meris/rules/paths.md",
            action="create",
            content=content,
        ),
        signals=[ev.get("kind", "")],
        verify=["meris harness check"],
        target_failure="Invalid path prefix (e.g. meris/README.md) or layout mismatch",
        expected_effect="Use README.md at repo root per AGENTS.md",
        regression_risk="Low — paths rule append",
    )


def _harness_check_proposal(ev: dict[str, Any]) -> Proposal:
    marker = "<!-- ratchet:L-harness-check -->"
    content = f"""{marker}

## Ratchet (auto)

- 任务结束前运行 `meris harness check` 与 AGENTS DoD（pytest）。
- 路径用 `README.md`，import 用 `from meris....`；禁止 `forge/`、`meris/README.md`。
- 触发: {ev.get("detail", "")[:120]}
"""
    return Proposal(
        id=new_proposal_id(),
        lesson="L-harness-check",
        summary="Harness 静态检查或 DoD 失败（路径/import/pytest）",
        target=ProposalTarget(
            path=".meris/rules/paths.md",
            action="append",
            content=content,
        ),
        signals=[ev.get("kind", "")],
        verify=["meris harness check"],
        target_failure="Harness check or DoD failed (import/path/pytest)",
        expected_effect="Run DoD before finishing; fix paths and imports",
        regression_risk="Low — reinforces existing DoD",
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

    if kind in ("harness_check_fail", "dod_failed", "sensor_fail"):
        if any(
            x in det
            for x in ("import:forge", "paths:readme", "harness check", "meris/readme", "forge/")
        ):
            if not _lesson_applied(workspace, "L-harness-check", existing):
                return _harness_check_proposal(ev)

    if kind == "benchmark_fail" and (
        "meris/readme" in det or "readme.md" in det and "missing:" in det
    ):
        if not _lesson_applied(workspace, "L-path", existing):
            return _paths_proposal(ev)

    if kind in ("benchmark_fail", "permission_denied", "approve_denied"):
        if "block" in det or "denied" in det or "permission" in det or "blocked" in det:
            if "readme" in det or "meris/" in det or "blockedpaths" in det.replace(" ", ""):
                if not _lesson_applied(workspace, "L-cwd", existing):
                    return _workspace_proposal(ev)

    if kind == "benchmark_fail" and "meris/readme" in det:
        if not _lesson_applied(workspace, "L-path", existing):
            return _paths_proposal(ev)

    if "meris/readme" in task:
        if not _lesson_applied(workspace, "L-path", existing):
            return _paths_proposal(ev)

    if kind == "max_turns":
        if not _lesson_applied(workspace, "L-stall", existing):
            return _stall_proposal(ev)

    return None


def _stall_proposal(ev: dict[str, Any]) -> Proposal:
    marker = "<!-- ratchet:L-stall -->"
    content = f"""{marker}

## Ratchet (auto)

- 达到 max_turns 仍未交付时：先写产物/结论，再探索；避免长时间无产出探索。
- 触发: {ev.get("detail", "")[:120]}
"""
    return Proposal(
        id=new_proposal_id(),
        lesson="L-stall",
        summary="Turn 用尽仍未完成 — 探索过长或无产物",
        target=ProposalTarget(
            path=".meris/rules/workspace.md",
            action="append",
            content=content,
        ),
        signals=[ev.get("kind", "")],
        verify=[],
        target_failure="Agent exhausted turns without deliverable",
        expected_effect="Prioritize artifact delivery before deep exploration",
        regression_risk="Low",
    )


def classify_events(workspace: Path, events: list[dict[str, Any]]) -> list[Proposal]:
    created: list[Proposal] = []
    for ev in events:
        p = classify_event(workspace, ev, created)
        if p:
            created.append(p)
    return created
