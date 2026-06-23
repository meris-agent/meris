"""Native benchmark smoke tasks."""

from __future__ import annotations

from pathlib import Path

from meris.benchmark import _run_local_task, filter_benchmark_tasks, load_benchmark_tasks


def test_filter_benchmark_tasks_excludes_native_by_default() -> None:
    root = Path(__file__).resolve().parents[1]
    tasks = load_benchmark_tasks(root / "scripts" / "benchmark" / "tasks.json")
    filtered = filter_benchmark_tasks(tasks)
    assert all(not t.id.startswith("native_") for t in filtered)
    assert len(filtered) == 8


def test_filter_benchmark_tasks_native_only() -> None:
    root = Path(__file__).resolve().parents[1]
    tasks = load_benchmark_tasks(root / "scripts" / "benchmark" / "tasks.json")
    native = filter_benchmark_tasks(tasks, native_only=True)
    assert len(native) == 3
    assert {t.id for t in native} == {
        "native_system_prompt",
        "native_dod_bridge",
        "native_run_entry",
    }


def test_native_system_prompt_local(workspace: Path) -> None:
    out, status, detail = _run_local_task(workspace, "native_system_prompt")
    assert status == "pass", detail
    assert "Meris" in out


def test_native_dod_bridge_local(workspace: Path) -> None:
    out, status, detail = _run_local_task(workspace, "native_dod_bridge")
    assert status == "pass", detail
    assert "ratchet" in out.lower()
