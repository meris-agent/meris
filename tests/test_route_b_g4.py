"""Live benchmark default tasks (native loop + 3 agent tasks)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_route_b_live_task_ids() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from run_benchmark_live import ROUTE_B_LIVE_TASKS, select_live_agent_tasks

    from meris.benchmark import load_benchmark_tasks

    tasks_path = ROOT / "scripts" / "benchmark" / "tasks.json"
    all_tasks = load_benchmark_tasks(tasks_path)
    selected = select_live_agent_tasks(all_tasks)
    ids = [t.id for t in selected]
    assert ids == list(ROUTE_B_LIVE_TASKS)
    assert len(ids) == 3


def test_select_live_filter_overrides_default() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from run_benchmark_live import select_live_agent_tasks

    from meris.benchmark import load_benchmark_tasks

    all_tasks = load_benchmark_tasks(ROOT / "scripts" / "benchmark" / "tasks.json")
    selected = select_live_agent_tasks(all_tasks, filter_prefixes=["read_hello"])
    assert [t.id for t in selected] == ["read_hello"]


def test_env_example_has_native_loop_auto() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "MERIS_NATIVE_LOOP=auto" in text
    assert text.index("MERIS_NATIVE_LOOP=auto") < text.find("MERIS_NATIVE_LOOP=0")


def test_init_env_template_has_native_loop() -> None:
    text = (ROOT / "templates" / "env.example").read_text(encoding="utf-8")
    assert "MERIS_NATIVE_LOOP=auto" in text


def test_doctor_native_loop_ok_when_auto(workspace, monkeypatch) -> None:
    from meris.harness.doctor import check_harness
    from meris.native import find_native_binary, native_loop_enabled

    if not find_native_binary():
        pytest.skip("meris-rs not built")
    monkeypatch.setenv("MERIS_NATIVE_LOOP", "auto")
    monkeypatch.delenv("MERIS_NATIVE", raising=False)
    if not native_loop_enabled():
        pytest.skip("agent subcommand not available")
    results = check_harness(workspace)
    native = next(r for r in results if r.name == "native loop")
    assert native.status == "ok"
    assert "auto" in native.detail.lower()


def test_doctor_warns_when_loop_unset(workspace, monkeypatch) -> None:
    from meris.harness.doctor import check_harness
    from meris.native import find_native_binary

    if not find_native_binary():
        pytest.skip("meris-rs not built")
    monkeypatch.delenv("MERIS_NATIVE_LOOP", raising=False)
    results = check_harness(workspace)
    native = next(r for r in results if r.name == "native loop")
    assert native.status == "warn"


def test_init_harness_creates_env(tmp_path) -> None:
    from meris.cli import init_harness

    init_harness(tmp_path)
    env = tmp_path / ".env"
    assert env.is_file()
    assert "MERIS_NATIVE_LOOP=auto" in env.read_text(encoding="utf-8")
