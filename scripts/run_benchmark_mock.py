"""Offline benchmark smoke — mock provider, no LLM."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from meris.benchmark import filter_benchmark_tasks, load_benchmark_tasks, run_benchmark, summarize


class MockProvider:
    model = "mock"

    async def chat(self, messages, tools=None):
        user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        low = user.lower()
        if "hello.py" in user:
            return {"content": "hello.py prints hello", "tool_calls": None}
        if "checkbox" in low or "plan" in low:
            return {"content": "- [ ] a\n- [ ] b\n- [ ] c", "tool_calls": None}
        if "pytest command" in low or "definition of done" in low:
            return {"content": 'pytest tests/ -m "not integration" -q', "tool_calls": None}
        if "paths.md" in low and "readme" in low:
            return {"content": "README.md at repo root", "tool_calls": None}
        if "architecture.md" in low or "import prefix" in low:
            return {"content": "from meris.xxx import y", "tool_calls": None}
        if "builtin" in low:
            return {"content": "read_file glob grep git_status bash", "tool_calls": None}
        return {"content": "read_file glob grep", "tool_calls": None}


async def main() -> int:
    argv = sys.argv[1:]
    native_only = "--native-only" in argv
    include_native = "--native" in argv or native_only
    root = Path(__file__).resolve().parents[1]
    all_tasks = load_benchmark_tasks(root / "scripts" / "benchmark" / "tasks.json")
    tasks = filter_benchmark_tasks(
        all_tasks,
        include_native=include_native,
        native_only=native_only,
    )
    if not tasks:
        print("No benchmark tasks selected")
        return 1
    results = await run_benchmark(root, tasks, provider=MockProvider())
    s = summarize(results)
    label = "native-only" if native_only else ("mock+native" if include_native else "mock")
    for r in results:
        tag = "PASS" if r.status == "pass" else "FAIL"
        detail = (r.detail or "")[:70]
        print(f"  [{tag}] {r.task_id}: {detail}")
    print(f"\nBenchmark ({label}): {s['passed']}/{s['total']} passed ({s['rate']:.0f}%)")
    return 0 if s["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
