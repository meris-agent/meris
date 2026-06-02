"""Phase B — spec workflow, event hooks, benchmark, session prune."""

from __future__ import annotations

from pathlib import Path

import pytest

from meris.benchmark import load_benchmark_tasks, run_benchmark, summarize
from meris.harness.event_hooks import _path_matches
from meris.harness.sessions import prune_sessions, save_session, SessionRecord
from meris.harness.spec import get_next_phase, init_spec, phase_is_complete, spec_status


class _MockProvider:
    model = "mock"

    async def chat(self, messages, tools=None):
        user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        if "hello.py" in user:
            return {"content": "hello.py prints hello", "tool_calls": None}
        if "checkbox" in user.lower() or "plan" in user.lower():
            return {"content": "- [ ] task one\n- [ ] task two\n- [ ] task three", "tool_calls": None}
        return {"content": "read_file glob grep git_status", "tool_calls": None}


def test_spec_init_and_next_phase(workspace: Path) -> None:
    tpl = Path(__file__).resolve().parent.parent / "templates" / "spec"
    init_spec(workspace, "auth module", tpl_dir=tpl)
    phase = get_next_phase(workspace)
    assert phase is not None
    assert phase.name == "requirements"
    rows = spec_status(workspace)
    assert any(r[0] == "requirements" and r[1] == "pending" for r in rows)


def test_phase_is_complete() -> None:
    assert phase_is_complete("# Done\n\n" + "x" * 120) is True
    assert phase_is_complete("# TBD\n\n(TBD)") is False


def test_path_matches_glob() -> None:
    assert _path_matches("*.py", "src/main.py") is True
    assert _path_matches("*.py", "src/main.ts") is False


def test_prune_sessions(workspace: Path) -> None:
    for i in range(5):
        save_session(
            workspace,
            SessionRecord(id=f"id{i:02d}", task=f"t{i}", mode="ask"),
        )
    deleted = prune_sessions(workspace, keep=2)
    assert deleted == 3


def test_load_benchmark_tasks() -> None:
    tf = Path(__file__).resolve().parent.parent / "scripts" / "benchmark" / "tasks.json"
    tasks = load_benchmark_tasks(tf)
    assert len(tasks) >= 2
    assert tasks[0].id


@pytest.mark.asyncio
async def test_benchmark_mock_run(workspace: Path) -> None:
    from meris.benchmark import BenchmarkTask

    tasks = [
        BenchmarkTask(id="t1", task="What does hello.py print?", expect=["hello"], max_turns=4),
    ]
    results = await run_benchmark(workspace, tasks, provider=_MockProvider())
    assert results[0].status == "pass"
    assert summarize(results)["rate"] == 100.0


@pytest.mark.asyncio
async def test_benchmark_plan_includes_saved_plan(workspace: Path) -> None:
    from meris.benchmark import BenchmarkTask

    tasks = [
        BenchmarkTask(
            id="plan",
            task="Plan a feature. 3 checkbox tasks only.",
            mode="plan",
            expect=["- [ ]"],
            max_turns=4,
        ),
    ]
    results = await run_benchmark(workspace, tasks, provider=_MockProvider())
    assert results[0].status == "pass"
    plan_file = workspace / ".meris" / "plan" / "tasks.md"
    assert plan_file.is_file()
    assert "- [ ]" in plan_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_on_save_hook_runs(workspace: Path, monkeypatch) -> None:
    from meris.harness.event_hooks import run_event_hooks

    calls: list[str] = []

    async def fake_run(workspace, command, env):
        from meris.harness.hooks import HookResult

        calls.append(env.get("MERIS_SAVED_PATH", ""))
        return HookResult(block=False, message="saved")

    monkeypatch.setattr("meris.harness.event_hooks._run_hook_command", fake_run)
    settings = {"hooks": {"onSave": [{"command": "echo ok", "matcher": "*.py"}]}}
    await run_event_hooks(workspace, settings, "onSave", path="foo.py")
    assert calls == ["foo.py"]
