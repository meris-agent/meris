"""Tests for harness gc, handoff, verify, fingerprint."""

from __future__ import annotations

from pathlib import Path

import pytest

from meris.harness.gc import gc_has_warnings, run_harness_gc
from meris.harness.handoff import handoff_path, write_session_handoff
from meris.harness.ratchet.fingerprint import harness_fingerprint
from meris.harness.ratchet.proposal import Proposal, ProposalTarget
from meris.harness.ratchet.verify import run_proposal_verify
from meris.harness.sessions import SessionRecord


def test_harness_fingerprint_changes_on_rule_edit(workspace: Path) -> None:
    fp1 = harness_fingerprint(workspace)
    rule = workspace / ".meris" / "rules" / "fp-test.md"
    rule.parent.mkdir(parents=True, exist_ok=True)
    rule.write_text("# test\n", encoding="utf-8")
    fp2 = harness_fingerprint(workspace)
    assert fp1 != fp2


def test_write_session_handoff(workspace: Path) -> None:
    rec = SessionRecord(
        id="sess-handoff-1",
        task="fix tests",
        mode="run",
        max_turns=10,
        turn=10,
        status="max_turns",
        workspace=str(workspace),
        messages=[
            {"role": "assistant", "content": "still working"},
        ],
    )
    path = write_session_handoff(workspace, rec, status="max_turns", verifier_output="pytest failed")
    assert path == handoff_path(workspace)
    text = path.read_text(encoding="utf-8")
    assert "sess-handoff-1" in text
    assert "pytest failed" in text
    assert "剩余风险" in text


def test_handoff_skips_completed(workspace: Path) -> None:
    rec = SessionRecord(id="x", task="t", mode="run", max_turns=5, turn=1, status="completed")
    assert write_session_handoff(workspace, rec, status="completed") is None


def test_harness_gc_ok(workspace: Path) -> None:
    findings = run_harness_gc(workspace)
    assert findings
    assert not gc_has_warnings(findings) or all(f.severity == "info" for f in findings if f.id == "ok")


def test_harness_gc_warn_large_agents(workspace: Path) -> None:
    agents = workspace / "AGENTS.md"
    agents.write_text("x" * 9000, encoding="utf-8")
    findings = run_harness_gc(workspace)
    assert any(f.id == "agents-size" for f in findings)
    assert gc_has_warnings(findings)


def test_run_proposal_verify_harness_check(workspace: Path) -> None:
    p = Proposal(
        id="v-1",
        lesson="L-test",
        summary="test",
        target=ProposalTarget(path=".meris/rules/x.md", content=""),
        verify=["meris harness check"],
    )
    ok, out = run_proposal_verify(workspace, p)
    assert ok is True
    assert "AGENTS.md" in out or "ok" in out.lower()


def test_apply_verify_reverts_on_fail(workspace: Path) -> None:
    from meris.harness.ratchet import apply_proposal

    skill = workspace / ".meris" / "skills" / "verify-fail.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# original\n", encoding="utf-8")
    p = Proposal(
        id="ratchet-verify-fail",
        lesson="L-verify",
        summary="should revert",
        target=ProposalTarget(
            path=".meris/skills/verify-fail.md",
            action="append",
            content="<!-- ratchet:L-verify -->\n\n## bad\n",
        ),
        verify=["meris benchmark run --filter nonexistent_task_xyz"],
    )
    with pytest.raises(ValueError, match="Verify failed"):
        apply_proposal(workspace, p, verify=True, update_progress=False)
    assert "original" in skill.read_text(encoding="utf-8")
    assert "## bad" not in skill.read_text(encoding="utf-8")


def test_load_handoff_in_system_prompt(workspace: Path) -> None:
    from meris.harness.guides import build_system_prompt
    from meris.harness.handoff import handoff_path

    handoff_path(workspace).parent.mkdir(parents=True, exist_ok=True)
    handoff_path(workspace).write_text(
        "# Session handoff\n\n## Context\n- **Status**: max_turns\n",
        encoding="utf-8",
    )
    prompt = build_system_prompt(workspace, mode="run")
    assert "Prior session handoff" in prompt
    assert "max_turns" in prompt


def test_regression_compare_no_regression(workspace: Path) -> None:
    from meris.benchmark import BenchmarkResult
    from meris.benchmark_regression import compare_to_baseline

    baseline = {"tasks": {"a": {"status": "pass", "split": "held_in"}}}
    results = [BenchmarkResult("a", "pass", "", "ok")]
    ok, msgs, stats = compare_to_baseline(results, baseline)
    assert ok is True
    assert stats["regressed"] == 0


def test_regression_detects_regression(workspace: Path) -> None:
    from meris.benchmark import BenchmarkResult
    from meris.benchmark_regression import compare_to_baseline

    baseline = {"tasks": {"a": {"status": "pass", "split": "held_out"}}}
    results = [BenchmarkResult("a", "fail", "", "broken")]
    ok, msgs, _stats = compare_to_baseline(results, baseline)
    assert ok is False
    assert any("REGRESSION" in m for m in msgs)


def test_cluster_failures_from_session(workspace: Path) -> None:
    from meris.harness.ratchet.cluster import cluster_failures
    from meris.harness.sessions import SessionRecord, save_session

    rec = SessionRecord(
        id="clust-1",
        task="long explore",
        mode="run",
        status="max_turns",
        turn=10,
        max_turns=10,
        messages=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "read_file", "arguments": "{}"}},
                ],
            }
        ],
    )
    save_session(workspace, rec)
    clusters = cluster_failures(workspace, min_count=1)
    assert any(c.signature in ("stall_max_turns", "stall_explore_no_write") for c in clusters)


def test_environment_in_prompt(workspace: Path) -> None:
    from meris.harness.environment import load_environment_for_prompt
    from meris.harness.guides import build_system_prompt

    env_dir = workspace / ".meris" / "environments"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "test.yaml").write_text("name: test-env\ngoal: verify changes\n", encoding="utf-8")
    assert "test-env" in load_environment_for_prompt(workspace)
    assert "Environment contract" in build_system_prompt(workspace)


def test_save_and_load_baseline(workspace: Path) -> None:
    from meris.benchmark import BenchmarkResult, BenchmarkTask
    from meris.benchmark_regression import baseline_path, load_baseline, save_baseline

    tasks = [BenchmarkTask(id="t1", local="harness_check", split="held_in")]
    results = [BenchmarkResult("t1", "pass", "", "ok")]
    path = save_baseline(workspace, results, tasks)
    assert path == baseline_path(workspace)
    loaded = load_baseline(workspace)
    assert loaded and loaded["tasks"]["t1"]["status"] == "pass"

