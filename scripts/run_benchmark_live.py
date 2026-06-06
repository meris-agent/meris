#!/usr/bin/env python3
"""Live benchmark — real LLM agent tasks (requires API key).

Usage:
  python scripts/run_benchmark_live.py
  python scripts/run_benchmark_live.py --filter read_hello
  python scripts/run_benchmark_live.py --all-agent
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _has_api_key() -> bool:
    from meris.provider.resolve import resolve_provider_config

    cfg = resolve_provider_config()
    key = (cfg.api_key or "").strip()
    return bool(key) and key not in ("not-needed", "")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run live Meris benchmark tasks")
    parser.add_argument(
        "--filter",
        "-k",
        action="append",
        default=[],
        help="Task id prefix (repeatable). Default: read_hello, docs_smoke",
    )
    parser.add_argument(
        "--all-agent",
        action="store_true",
        help="Run all non-local agent tasks (costs more API)",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=ROOT,
        help="Workspace root",
    )
    args = parser.parse_args()

    if not _has_api_key():
        print(
            "No API key — set MERIS_PROVIDER + key env (see meris models list).\n"
            "Offline alternative: python scripts/run_benchmark_mock.py",
            file=sys.stderr,
        )
        return 1

    from meris.benchmark import load_benchmark_tasks, run_benchmark, summarize
    from meris.provider import get_provider
    from meris.provider.resolve import resolve_provider_config

    cfg = resolve_provider_config()
    provider = get_provider(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model,
    )

    tasks_path = ROOT / "scripts" / "benchmark" / "tasks.json"
    all_tasks = load_benchmark_tasks(tasks_path)
    agent_tasks = [t for t in all_tasks if not t.local]

    if args.all_agent:
        selected = agent_tasks
    elif args.filter:
        prefixes = args.filter
        selected = [
            t
            for t in agent_tasks
            if any(t.id == p or t.id.startswith(p) for p in prefixes)
        ]
    else:
        defaults = ("read_hello", "docs_smoke")
        selected = [t for t in agent_tasks if t.id in defaults]

    if not selected:
        print("No agent tasks matched filter.", file=sys.stderr)
        return 1

    print(f"Live benchmark: {len(selected)} task(s) via {cfg.preset_id}/{cfg.model}")
    ws = args.cwd.resolve()
    results = await run_benchmark(ws, selected, provider=provider)
    summary = summarize(results)
    for r in results:
        tag = "PASS" if r.status == "pass" else r.status.upper()
        print(f"  [{tag}] {r.task_id}: {(r.detail or '')[:80]}")
    print(f"\nBenchmark: {summary['passed']}/{summary['total']} passed ({summary['rate']:.0f}%)")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
