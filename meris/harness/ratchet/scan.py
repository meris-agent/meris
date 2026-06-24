"""Scan events and sessions → proposals."""

from __future__ import annotations

import json
from pathlib import Path

from meris.harness.paths import harness_root
from meris.harness.ratchet.classify import classify_events
from meris.harness.ratchet.events import load_events, record_event
from meris.harness.ratchet.proposal import Proposal, list_proposals, save_proposal


def ingest_session_failures(workspace: Path) -> int:
    """Backfill events from recent failed sessions."""
    sessions_dir = harness_root(workspace) / "sessions"
    if not sessions_dir.is_dir():
        return 0
    n = 0
    for fp in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        status = data.get("status", "")
        if status not in ("dod_failed", "error", "max_turns"):
            continue
        record_event(
            workspace,
            status,
            session=data.get("id", fp.stem),
            task=data.get("task", ""),
            detail=f"session status={status}",
            tags=["session", status],
        )
        n += 1
    return n


def scan_workspace(
    workspace: Path,
    *,
    since_days: int | None = 7,
    ingest_sessions: bool = False,
) -> list[Proposal]:
    """Classify recent events into new pending proposals."""
    if ingest_sessions:
        ingest_session_failures(workspace)
    events = load_events(workspace, since_days=since_days)
    pending = list_proposals(workspace, status="pending")
    new_props = classify_events(workspace, events)

    saved: list[Proposal] = []
    for p in new_props:
        if any(x.lesson == p.lesson and x.status == "pending" for x in pending):
            continue
        save_proposal(workspace, p)
        saved.append(p)
        pending.append(p)
    return saved
