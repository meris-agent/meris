"""After-run ratchet hook (--ratchet)."""

from __future__ import annotations

from pathlib import Path

from meris.harness.ratchet.profile import rebuild_profile
from meris.harness.ratchet.scan import scan_workspace
from meris.harness.sessions import list_sessions, load_session


def ratchet_post_run(workspace: Path, *, session_id: str | None = None) -> tuple[int, str | None]:
    """Rebuild profile + scan events. Returns (new_proposals, user_message)."""
    ws = workspace.resolve()
    profile_path = rebuild_profile(ws, since_days=30)

    sid = session_id
    if not sid:
        sessions = list_sessions(ws)
        if sessions:
            sid = sessions[0].id

    failed = False
    if sid:
        rec = load_session(ws, sid)
        if rec and rec.status in ("dod_failed", "error", "denied", "cancelled"):
            failed = rec.status != "cancelled"

    created = scan_workspace(ws, since_days=14 if failed else 3)

    from meris.harness.ratchet import list_proposals

    pending = list_proposals(ws, status="pending")
    parts: list[str] = []
    if profile_path:
        parts.append("[ratchet] profile updated")
    if created:
        parts.append(f"[ratchet] {len(created)} new proposal(s) — meris ratchet review")
    elif pending:
        parts.append(f"[ratchet] {len(pending)} pending — meris ratchet review")
    elif failed:
        parts.append("[ratchet] meris ratchet scan")
    msg = " · ".join(parts) if parts else None
    return len(created), msg
