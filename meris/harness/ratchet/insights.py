"""Ratchet insights — habit candidates from session history (human confirm)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from meris.harness.ratchet.paths import insights_dir


@dataclass
class Insight:
    id: str
    kind: str  # user_habit | project_preference
    pattern: str
    question: str
    count: int
    evidence: list[str] = field(default_factory=list)
    suggested_target: str = ".meris/rules/user-prefs.md"
    suggested_content: str = ""
    lesson: str = ""
    status: str = "pending"  # pending | dismissed | accepted
    source: str = "rule"  # rule | llm
    created: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Insight:
        return cls(
            id=data["id"],
            kind=data.get("kind", "user_habit"),
            pattern=data.get("pattern", ""),
            question=data.get("question", ""),
            count=int(data.get("count", 0)),
            evidence=list(data.get("evidence") or []),
            suggested_target=data.get("suggested_target", ".meris/rules/user-prefs.md"),
            suggested_content=data.get("suggested_content", ""),
            lesson=data.get("lesson", ""),
            status=data.get("status", "pending"),
            source=data.get("source", "rule"),
            created=data.get("created", ""),
        )


def new_insight_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"insight-{ts}-{uuid.uuid4().hex[:6]}"


def _jsonl_path(workspace: Path, status: str) -> Path:
    d = insights_dir(workspace)
    name = {"pending": "pending.jsonl", "dismissed": "dismissed.jsonl", "accepted": "accepted.jsonl"}.get(
        status, "pending.jsonl"
    )
    return d / name


def _read_jsonl(path: Path) -> list[Insight]:
    if not path.is_file():
        return []
    out: list[Insight] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(Insight.from_dict(json.loads(line)))
        except (json.JSONDecodeError, KeyError):
            continue
    return out


def _write_jsonl(path: Path, rows: list[Insight]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(r.to_dict(), ensure_ascii=False) for r in rows)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def list_insights(workspace: Path, *, status: str = "pending") -> list[Insight]:
    return _read_jsonl(_jsonl_path(workspace, status))


def load_insight(workspace: Path, insight_id: str) -> Insight | None:
    for st in ("pending", "dismissed", "accepted"):
        for ins in list_insights(workspace, status=st):
            if ins.id == insight_id:
                return ins
    return None


def save_insight(workspace: Path, insight: Insight) -> Path:
    path = _jsonl_path(workspace, insight.status)
    rows = _read_jsonl(path)
    rows = [r for r in rows if r.id != insight.id]
    rows.append(insight)
    _write_jsonl(path, rows)
    return path


def _remove_insight(workspace: Path, insight_id: str) -> Insight | None:
    for st in ("pending", "dismissed", "accepted"):
        path = _jsonl_path(workspace, st)
        rows = _read_jsonl(path)
        kept: list[Insight] = []
        found: Insight | None = None
        for r in rows:
            if r.id == insight_id:
                found = r
            else:
                kept.append(r)
        if found:
            _write_jsonl(path, kept)
            return found
    return None


def move_insight(workspace: Path, insight_id: str, new_status: str) -> Insight | None:
    ins = _remove_insight(workspace, insight_id)
    if not ins:
        return None
    ins.status = new_status
    save_insight(workspace, ins)
    return ins


def count_pending_insights(workspace: Path) -> int:
    return len(list_insights(workspace, status="pending"))
