"""Run proposal verify steps — promotion gate for Ratchet apply."""

from __future__ import annotations

import asyncio
from pathlib import Path

from meris.harness.ratchet.proposal import Proposal


def _parse_verify_cmd(cmd: str) -> tuple[str, str | None]:
    """Return (kind, filter) for supported meris verify strings."""
    parts = cmd.strip().split()
    if not parts:
        return ("unknown", None)
    if parts[0] == "meris" and len(parts) > 1:
        if parts[1] == "harness" and len(parts) > 2 and parts[2] == "check":
            return ("harness_check", None)
        if parts[1] == "benchmark" and "run" in parts:
            filt = None
            if "--filter" in parts:
                filt = parts[parts.index("--filter") + 1]
            return ("benchmark", filt)
    return ("shell", cmd)


def run_proposal_verify(workspace: Path, proposal: Proposal) -> tuple[bool, str]:
    """Run all verify steps; return (ok, combined output)."""
    if not proposal.verify:
        return True, "no verify steps"

    ws = workspace.resolve()
    outputs: list[str] = []
    for cmd in proposal.verify:
        kind, arg = _parse_verify_cmd(cmd)
        if kind == "harness_check":
            from meris.harness.check import format_check_summary, harness_check_failed, run_harness_check

            results = run_harness_check(ws)
            out = format_check_summary(results)
            outputs.append(out)
            if harness_check_failed(results):
                return False, "\n".join(outputs)
        elif kind == "benchmark":
            from meris.benchmark import (
                filter_benchmark_tasks,
                load_benchmark_tasks,
                resolve_benchmark_tasks_path,
                run_benchmark,
                summarize,
            )

            default = Path(__file__).resolve().parents[3] / "scripts" / "benchmark" / "tasks.json"
            tf = resolve_benchmark_tasks_path(ws, default)
            tasks = load_benchmark_tasks(tf)
            tasks = filter_benchmark_tasks(tasks, include_native=False)
            if arg:
                tasks = [t for t in tasks if t.id == arg or t.id.startswith(arg)]
            if arg and not tasks:
                return False, f"no benchmark tasks for filter: {arg}"

            async def _run():
                return await run_benchmark(ws, tasks, provider=None)

            results = asyncio.run(_run())
            summary = summarize(results)
            lines = [f"benchmark {r.task_id}: {r.status} — {r.detail[:120]}" for r in results]
            outputs.append("\n".join(lines))
            outputs.append(
                f"pass rate: {summary['passed']}/{summary['total']} ({summary['rate']:.0f}%)"
            )
            if summary["failed"] > 0:
                return False, "\n".join(outputs)
        else:
            outputs.append(f"unsupported verify command: {cmd}")
            return False, "\n".join(outputs)

    return True, "\n".join(outputs)
