"""Append-only ratchet event stream."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from meris.harness.ratchet.paths import events_file

_MAX_DEDUPE_SCAN = 80


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fingerprint(kind: str, task_id: str, detail: str, task: str) -> str:
    raw = f"{kind}|{task_id}|{task[:120]}|{detail[:300]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _recent_fingerprints(workspace: Path) -> set[str]:
    fps: set[str] = set()
    for ev in load_events(workspace)[-_MAX_DEDUPE_SCAN:]:
        fp = ev.get("fp")
        if fp:
            fps.add(fp)
    return fps


def args_summary(args: dict[str, Any], *, max_len: int = 120) -> str:
    """Safe one-line summary for events (no full secrets)."""
    if not args:
        return "{}"
    parts: list[str] = []
    for k, v in list(args.items())[:6]:
        s = str(v)
        if "key" in k.lower() or "token" in k.lower() or "password" in k.lower():
            s = "***"
        elif len(s) > 40:
            s = s[:37] + "..."
        parts.append(f"{k}={s}")
    out = ", ".join(parts)
    return out[:max_len]


def record_event(
    workspace: Path,
    kind: str,
    *,
    session: str = "",
    task: str = "",
    task_id: str = "",
    detail: str = "",
    tool: str = "",
    args_summary_text: str = "",
    tags: list[str] | None = None,
    extra: dict[str, Any] | None = None,
    dedupe: bool = True,
) -> bool:
    """Append one JSON line. Returns False if skipped as duplicate."""
    detail = detail[:2000]
    fp = _fingerprint(kind, task_id, detail, task)
    if dedupe and fp in _recent_fingerprints(workspace):
        return False

    row: dict[str, Any] = {
        "ts": _now(),
        "kind": kind,
        "fp": fp,
        "session": session,
        "task": task[:500],
        "task_id": task_id,
        "detail": detail,
        "tool": tool,
        "args_summary": args_summary_text[:200],
        "tags": tags or [],
    }
    if extra:
        row.update(extra)
    path = events_file(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return True


def load_events(workspace: Path, *, since_days: int | None = None) -> list[dict[str, Any]]:
    path = events_file(workspace)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if since_days is None:
        return rows
    cutoff = datetime.now(timezone.utc).timestamp() - since_days * 86400
    out: list[dict[str, Any]] = []
    for r in rows:
        ts = r.get("ts", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.timestamp() >= cutoff:
                out.append(r)
        except ValueError:
            out.append(r)
    return out


def count_events(workspace: Path, *, since_days: int = 7) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ev in load_events(workspace, since_days=since_days):
        k = ev.get("kind", "unknown")
        counts[k] = counts.get(k, 0) + 1
    return counts
