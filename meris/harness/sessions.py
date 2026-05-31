"""Session persistence — save/resume agent conversations."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from meris.harness.paths import harness_root


def _sessions_dir(workspace: Path) -> Path:
    d = harness_root(workspace) / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class SessionRecord:
    id: str
    task: str
    mode: str
    status: str = "running"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    messages: list[dict[str, Any]] = field(default_factory=list)
    turn: int = 0
    max_turns: int = 30
    workspace: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionRecord:
        return cls(
            id=data["id"],
            task=data["task"],
            mode=data["mode"],
            status=data.get("status", "running"),
            created_at=data.get("created_at", _now()),
            updated_at=data.get("updated_at", _now()),
            messages=list(data.get("messages") or []),
            turn=int(data.get("turn", 0)),
            max_turns=int(data.get("max_turns", 30)),
            workspace=data.get("workspace", ""),
        )


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def session_path(workspace: Path, session_id: str) -> Path:
    return _sessions_dir(workspace) / f"{session_id}.json"


def save_session(workspace: Path, record: SessionRecord) -> Path:
    record.updated_at = _now()
    p = session_path(workspace, record.id)
    p.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load_session(workspace: Path, session_id: str) -> SessionRecord | None:
    p = session_path(workspace, session_id)
    if not p.is_file():
        return None
    return SessionRecord.from_dict(json.loads(p.read_text(encoding="utf-8")))


def delete_session(workspace: Path, session_id: str) -> bool:
    """Delete a session file. Returns True if deleted, False if not found."""
    p = session_path(workspace, session_id)
    if not p.is_file():
        return False
    p.unlink()
    return True


def prune_sessions(workspace: Path, *, keep: int = 20) -> int:
    """Delete oldest sessions beyond `keep`. Returns count deleted."""
    records = list_sessions(workspace)
    if len(records) <= keep:
        return 0
    deleted = 0
    for rec in records[keep:]:
        if delete_session(workspace, rec.id):
            deleted += 1
    return deleted


def list_sessions(workspace: Path) -> list[SessionRecord]:
    d = _sessions_dir(workspace)
    if not d.is_dir():
        return []
    records: list[SessionRecord] = []
    for fp in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            records.append(SessionRecord.from_dict(json.loads(fp.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, KeyError):
            continue
    return records
