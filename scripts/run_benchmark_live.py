#!/usr/bin/env python3
"""Live benchmark — real LLM agent tasks (requires API key).

Usage:
  python scripts/run_benchmark_live.py              # Route B default: 3 agent tasks
  python scripts/run_benchmark_live.py --route-b  # same as default
  python scripts/run_benchmark_live.py --filter read_hello
  python scripts/run_benchmark_live.py --all-agent
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Phase G4 — Route B live acceptance (read-only ask tasks, native loop friendly)
ROUTE_B_LIVE_TASKS: tuple[str, ...] = ("read_hello", "docs_smoke", "list_tools")


def select_live_agent_tasks(
    all_tasks,
    *,
    filter_prefixes: list[str] | None = None,
    all_agent: bool = False,
    task_ids: tuple[str, ...] | None = None,
):
    """Pick agent (non-local) benchmark tasks for live runs."""
    agent_tasks = [t for t in all_tasks if not t.local]
    if all_agent:
        return agent_tasks
    if filter_prefixes:
        return [
            t
            for t in agent_tasks
            if any(t.id == p or t.id.startswith(p) for p in filter_prefixes)
        ]
    ids = task_ids or ROUTE_B_LIVE_TASKS
    by_id = {t.id: t for t in agent_tasks}
    return [by_id[i] for i in ids if i in by_id]


def _has_api_key() -> bool:
    from meris.provider.resolve import resolve_provider_config

    cfg = resolve_provider_config()
    key = (cfg.api_key or "").strip()
    return bool(key) and key not in ("not-needed", "")


async def main() -> int:
    from meris.env import load_env

    load_env()

    parser = argparse.ArgumentParser(description="Run live Meris benchmark tasks")
    parser.add_argument(
        "--filter",
        "-k",
        action="append",
        default=[],
        help="Task id prefix (repeatable). Default: Route B 3 tasks",
    )
    parser.add_argument(
        "--route-b",
        action="store_true",
        help=f"Run Route B live tasks: {', '.join(ROUTE_B_LIVE_TASKS)}",
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
    provider = None
    from meris.native import native_loop_enabled

    if not native_loop_enabled():
        provider = get_provider(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model,
        )

    tasks_path = ROOT / "scripts" / "benchmark" / "tasks.json"
    all_tasks = load_benchmark_tasks(tasks_path)

    selected = select_live_agent_tasks(
        all_tasks,
        filter_prefixes=args.filter or None,
        all_agent=args.all_agent,
        task_ids=ROUTE_B_LIVE_TASKS if not args.filter and not args.all_agent else None,
    )

    if not selected:
        print("No agent tasks matched filter.", file=sys.stderr)
        return 1

    print(f"Live benchmark: {len(selected)} task(s) via {cfg.preset_id}/{cfg.model}")
    if native_loop_enabled():
        print("  (native loop via MERIS_NATIVE_LOOP=auto)")
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
