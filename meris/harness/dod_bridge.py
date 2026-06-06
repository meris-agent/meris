"""DoD failure bridge for meris-rs native agent (Phase F2-M3)."""

from __future__ import annotations

from pathlib import Path

from meris.harness.check import is_harness_check_failure
from meris.harness.ratchet import list_proposals
from meris.harness.ratchet.events import record_event


def handle_dod_failed(
    workspace: Path,
    *,
    session: str,
    task: str,
    mode: str,
    sensor_out: str,
) -> dict[str, object]:
    """Record ratchet event and return hint lines (parity with Python loop)."""
    kind = "dod_failed"
    if is_harness_check_failure(sensor_out):
        kind = "harness_check_fail"
    recorded = record_event(
        workspace,
        kind,
        session=session,
        task=task[:200],
        detail=sensor_out[:800],
        tags=["loop", mode, "dod"],
    )
    pending = list_proposals(workspace, status="pending")
    if pending:
        hint = f"[ratchet] {len(pending)} pending proposal(s) — meris ratchet review"
    else:
        hint = "[ratchet] meris ratchet scan — capture harness improvements"
    return {"recorded": recorded, "kind": kind, "hints": [hint]}
