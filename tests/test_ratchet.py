"""Ratchet — events, scan, apply, guides injection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meris.harness.guides import build_system_prompt
from meris.harness.memory import append_ratchet_summary_line, load_progress_for_prompt
from meris.harness.ratchet import (
    apply_proposal,
    is_allowed_target,
    list_proposals,
    load_proposal,
    record_event,
    reject_proposal,
    run_learn,
    scan_workspace,
)
from meris.harness.ratchet.apply import revert_proposal
from meris.harness.ratchet.proposal import Proposal, ProposalTarget


def test_record_and_scan_plan_format(workspace: Path) -> None:
    record_event(
        workspace,
        "benchmark_fail",
        task_id="plan_smoke",
        detail="missing: [ ]",
        tags=["plan", "format"],
    )
    created = scan_workspace(workspace, since_days=30)
    assert len(created) >= 1
    assert any(p.lesson == "L-format" for p in created)
    pending = list_proposals(workspace, status="pending")
    assert pending


def test_apply_appends_skill_and_guides_see_it(workspace: Path) -> None:
    skill = workspace / ".meris" / "skills" / "plan-format.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# Plan format\n", encoding="utf-8")

    p = Proposal(
        id="ratchet-test-001",
        lesson="L-format",
        summary="test",
        target=ProposalTarget(
            path=".meris/skills/plan-format.md",
            action="append",
            content="<!-- ratchet:L-format -->\n\n## Ratchet test\n- [ ] required\n",
        ),
    )
    apply_proposal(workspace, p)
    text = skill.read_text(encoding="utf-8")
    assert "ratchet:L-format" in text
    prompt = build_system_prompt(workspace)
    assert "plan-format" in prompt
    assert "ratchet:L-format" in text

    assert revert_proposal(workspace, p.id) is True
    restored = skill.read_text(encoding="utf-8")
    assert "Ratchet test" not in restored


def test_scan_dedupes_lesson(workspace: Path) -> None:
    record_event(workspace, "benchmark_fail", task_id="plan_smoke", detail="missing: [ ]")
    first = scan_workspace(workspace, since_days=30)
    second = scan_workspace(workspace, since_days=30)
    assert len(first) >= 1
    assert len(second) == 0


def test_scan_harness_check_fail(workspace: Path) -> None:
    record_event(
        workspace,
        "harness_check_fail",
        detail="import:forge: FAIL — meris/bad.py",
        tags=["dod"],
    )
    created = scan_workspace(workspace, since_days=30)
    assert any(p.lesson == "L-harness-check" for p in created)


def test_is_allowed_target() -> None:
    assert is_allowed_target(".meris/rules/foo.md") is True
    assert is_allowed_target("AGENTS.md") is False
    assert is_allowed_target("AGENTS.md", force_agents=True) is True
    assert is_allowed_target("meris/cli.py") is False


def test_event_dedupe(workspace: Path) -> None:
    ok1 = record_event(workspace, "benchmark_fail", task_id="x", detail="missing: [ ]")
    ok2 = record_event(workspace, "benchmark_fail", task_id="x", detail="missing: [ ]")
    assert ok1 is True
    assert ok2 is False


def test_apply_seeds_missing_skill(workspace: Path) -> None:
    skill = workspace / ".meris" / "skills" / "plan-format.md"
    assert not skill.exists()
    p = Proposal(
        id="ratchet-seed-001",
        lesson="L-format",
        summary="seed test",
        target=ProposalTarget(
            path=".meris/skills/plan-format.md",
            action="create",
            content="<!-- ratchet:L-format -->\n\n## Ratchet test\n",
        ),
    )
    apply_proposal(workspace, p, update_progress=False)
    text = skill.read_text(encoding="utf-8")
    assert "Plan 输出格式" in text or "Plan" in text
    assert "ratchet:L-format" in text


def test_progress_summary_and_prompt(workspace: Path) -> None:
    append_ratchet_summary_line(workspace, "always use - [ ] in plans")
    (workspace / "PROGRESS.md").write_text(
        (workspace / "PROGRESS.md").read_text(encoding="utf-8")
        + "\n\n## Session note (old)\n- **Task**: old\n",
        encoding="utf-8",
    )
    prompt = load_progress_for_prompt(workspace)
    assert "Ratchet 摘要" in prompt
    assert "- [ ]" in prompt


def test_reject_proposal(workspace: Path) -> None:
    record_event(workspace, "benchmark_fail", detail="missing: [ ]", task_id="p")
    created = scan_workspace(workspace, since_days=30)
    pid = created[0].id
    assert reject_proposal(workspace, pid)
    assert list_proposals(workspace, status="pending") == []


def test_parse_llm_proposals_json() -> None:
    from meris.harness.ratchet.analyze import proposals_from_llm_payload

    payload = {
        "proposals": [
            {
                "lesson": "L-analyze-test",
                "summary": "use checkboxes",
                "target": {
                    "path": ".meris/skills/plan-format.md",
                    "action": "append",
                    "content": "## rule\n- [ ] always",
                },
                "verify": [],
            },
            {
                "lesson": "bad",
                "summary": "hack",
                "target": {"path": "meris/cli.py", "action": "append", "content": "x"},
            },
        ]
    }
    props = proposals_from_llm_payload(payload)
    assert len(props) == 1
    assert "ratchet:L-analyze-test" in props[0].target.content


@pytest.mark.asyncio
async def test_analyze_workspace_mock(workspace: Path) -> None:
    from meris.harness.ratchet.analyze import analyze_workspace

    class _Mock:
        model = "mock"

        async def chat(self, messages, tools=None):
            return {
                "content": json.dumps(
                    {
                        "proposals": [
                            {
                                "lesson": "L-mock",
                                "summary": "mock rule",
                                "confidence": "high",
                                "target": {
                                    "path": ".meris/rules/mock.md",
                                    "action": "create",
                                    "content": "## Mock\n- test",
                                },
                            }
                        ]
                    }
                )
            }

    created = await analyze_workspace(workspace, provider=_Mock(), save=True)
    assert len(created) == 1
    assert (workspace / ".meris" / "ratchet" / "proposals" / f"{created[0].id}.json").is_file()


def test_learn_proposals(workspace: Path) -> None:
    (workspace / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (workspace / "meris").mkdir()
    (workspace / "meris" / "__init__.py").write_text("", encoding="utf-8")
    (workspace / "tests").mkdir()
    created = run_learn(workspace, init=True, save=False)
    lessons = {p.lesson for p in created}
    assert "L-learn-project" in lessons


def test_profile_from_events(workspace: Path) -> None:
    from meris.harness.guides import build_system_prompt
    from meris.harness.ratchet import rebuild_profile

    for _ in range(2):
        record_event(
            workspace,
            "approve_denied",
            tool="bash",
            args_summary_text="command=git push",
            detail="user denied",
        )
    path = rebuild_profile(workspace)
    assert path and path.is_file()
    prompt = build_system_prompt(workspace)
    assert "git push" in prompt or "拒绝" in prompt


def test_load_proposal_after_apply(workspace: Path) -> None:
    record_event(workspace, "benchmark_fail", detail="missing: [ ]", task_id="x")
    created = scan_workspace(workspace, since_days=30)
    pid = created[0].id
    skill = workspace / ".meris" / "skills" / "plan-format.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# x\n", encoding="utf-8")
    apply_proposal(workspace, created[0])
    assert load_proposal(workspace, pid) is not None
    assert list_proposals(workspace, status="pending") == []
