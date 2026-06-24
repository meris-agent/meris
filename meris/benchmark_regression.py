"""Benchmark regression — held-in/held-out vs baseline (Self-Harness promotion gate)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from meris.benchmark import BenchmarkResult, BenchmarkTask


def baseline_path(workspace: Path) -> Path:
    return workspace.resolve() / ".meris" / "benchmark" / "baseline.json"


def load_baseline(workspace: Path) -> dict[str, Any] | None:
    path = baseline_path(workspace)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_baseline(
    workspace: Path,
    results: list[BenchmarkResult],
    tasks: list[BenchmarkTask],
) -> Path:
    split_by_id = {t.id: t.split for t in tasks}
    path = baseline_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tasks": {
            r.task_id: {
                "status": r.status,
                "split": split_by_id.get(r.task_id, ""),
                "detail": r.detail[:200],
            }
            for r in results
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def compare_to_baseline(
    results: list[BenchmarkResult],
    baseline: dict[str, Any] | None,
) -> tuple[bool, list[str], dict[str, Any]]:
    """Return (ok, messages, stats). Fail if any task regressed pass→fail."""
    stats: dict[str, Any] = {
        "passed": sum(1 for r in results if r.status == "pass"),
        "total": len(results),
        "improved": 0,
        "regressed": 0,
        "new_tasks": 0,
    }
    messages: list[str] = []
    if not baseline:
        messages.append("no baseline — run with --update-baseline after a green run")
        return True, messages, stats

    base_tasks = baseline.get("tasks") or {}
    ok = True
    for r in results:
        prev = base_tasks.get(r.task_id)
        if not prev:
            stats["new_tasks"] += 1
            messages.append(f"  new task: {r.task_id} → {r.status}")
            continue
        prev_status = prev.get("status", "")
        if prev_status == "pass" and r.status != "pass":
            stats["regressed"] += 1
            ok = False
            split = prev.get("split", "")
            messages.append(
                f"  REGRESSION {r.task_id} ({split or 'no split'}): pass → {r.status}"
            )
        elif prev_status != "pass" and r.status == "pass":
            stats["improved"] += 1
            messages.append(f"  improved: {r.task_id} → pass")

    if stats["regressed"]:
        messages.insert(0, f"{stats['regressed']} task(s) regressed vs baseline")
    elif stats["improved"]:
        messages.insert(0, f"{stats['improved']} task(s) improved vs baseline")
    else:
        messages.insert(0, "no regression vs baseline")
    return ok, messages, stats
