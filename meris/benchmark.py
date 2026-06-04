"""Benchmark task runner — measure agent success rate."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from meris.loop import agent_loop


@dataclass
class BenchmarkTask:
    id: str
    task: str
    mode: str = "ask"
    expect: list[str] = field(default_factory=list)
    max_turns: int = 8


@dataclass
class BenchmarkResult:
    task_id: str
    status: str
    session_id: str = ""
    detail: str = ""


def load_benchmark_tasks(path: Path) -> list[BenchmarkTask]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks: list[BenchmarkTask] = []
    for item in data.get("tasks") or data:
        tasks.append(
            BenchmarkTask(
                id=item["id"],
                task=item["task"],
                mode=item.get("mode", "ask"),
                expect=list(item.get("expect") or []),
                max_turns=int(item.get("max_turns", 8)),
            )
        )
    return tasks


def _check_expectations(output: str, expect: list[str]) -> tuple[bool, str]:
    if not expect:
        return True, "no expectations"
    missing = [e for e in expect if e.lower() not in output.lower()]
    if missing:
        return False, f"missing: {', '.join(missing)}"
    return True, "all expectations met"


def _benchmark_output(workspace: Path, lines: list[str], task: BenchmarkTask) -> str:
    """Join streamed lines; for plan tasks also include saved plan file."""
    joined = "\n".join(lines)
    if task.mode == "plan":
        from meris.harness.plan import default_plan_path

        plan_path = default_plan_path(workspace)
        if plan_path.is_file():
            joined += "\n" + plan_path.read_text(encoding="utf-8")
    return joined


async def run_benchmark(
    workspace: Path,
    tasks: list[BenchmarkTask],
    *,
    provider=None,
    on_line=None,
    task_filter: str | None = None,
) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []
    for t in tasks:
        if task_filter and t.id != task_filter and not t.id.startswith(task_filter):
            continue
        lines: list[str] = []
        session_id = ""
        status = "pass"
        detail = ""
        plan_out: str | Path | None = "__default__" if t.mode == "plan" else None
        try:
            async for line in agent_loop(
                workspace,
                t.task,
                mode=t.mode,
                provider=provider,
                max_turns=t.max_turns,
                run_sensors_at_end=False,
                plan_output=plan_out,
            ):
                lines.append(line)
                if on_line:
                    on_line(t.id, line)
                if "session=" in line and session_id == "":
                    part = line.split("session=")[-1].split()[0]
                    session_id = part.strip()
        except Exception as e:
            status = "error"
            detail = str(e)
            results.append(BenchmarkResult(t.id, status, session_id, detail))
            continue

        joined = _benchmark_output(workspace, lines, t)
        ok, msg = _check_expectations(joined, t.expect)
        if not ok:
            status = "fail"
            detail = msg
            from meris.harness.ratchet import record_event

            record_event(
                workspace,
                "benchmark_fail",
                session=session_id,
                task_id=t.id,
                task=t.task[:200],
                detail=detail,
                tags=["benchmark", t.mode],
            )
        else:
            detail = msg
        results.append(BenchmarkResult(t.id, status, session_id, detail))
    return results


def summarize(results: list[BenchmarkResult]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.status == "pass")
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "rate": (passed / total * 100) if total else 0.0,
    }
