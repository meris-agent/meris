"""Ratchet proposal model (JSON on disk)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from meris.harness.ratchet.paths import applied_dir, proposals_dir


@dataclass
class ProposalTarget:
    path: str
    action: str = "append"  # append | create
    content: str = ""


@dataclass
class Proposal:
    id: str
    lesson: str
    summary: str
    target: ProposalTarget
    confidence: str = "high"
    signals: list[str] = field(default_factory=list)
    verify: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | applied | rejected
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    target_failure: str = ""
    expected_effect: str = ""
    regression_risk: str = ""
    harness_fp: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Proposal:
        t = data.get("target") or {}
        return cls(
            id=data["id"],
            lesson=data["lesson"],
            summary=data["summary"],
            target=ProposalTarget(
                path=t["path"],
                action=t.get("action", "append"),
                content=t.get("content", ""),
            ),
            confidence=data.get("confidence", "high"),
            signals=list(data.get("signals") or []),
            verify=list(data.get("verify") or []),
            status=data.get("status", "pending"),
            created=data.get("created", ""),
            target_failure=data.get("target_failure", ""),
            expected_effect=data.get("expected_effect", ""),
            regression_risk=data.get("regression_risk", ""),
            harness_fp=data.get("harness_fp", ""),
        )

    def marker(self) -> str:
        return f"<!-- ratchet:{self.lesson} -->"


def new_proposal_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"ratchet-{ts}-{uuid.uuid4().hex[:6]}"


def proposal_path(workspace: Path, proposal_id: str, *, applied: bool = False) -> Path:
    base = applied_dir(workspace) if applied else proposals_dir(workspace)
    return base / f"{proposal_id}.json"


def save_proposal(workspace: Path, proposal: Proposal, *, applied: bool = False) -> Path:
    path = proposal_path(workspace, proposal.id, applied=applied)
    path.write_text(json.dumps(proposal.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_proposal(workspace: Path, proposal_id: str) -> Proposal | None:
    for applied in (False, True):
        p = proposal_path(workspace, proposal_id, applied=applied)
        if p.is_file():
            return Proposal.from_dict(json.loads(p.read_text(encoding="utf-8")))
    return None


def list_proposals(workspace: Path, *, status: str | None = "pending") -> list[Proposal]:
    out: list[Proposal] = []
    for base, is_applied in ((proposals_dir(workspace), False), (applied_dir(workspace), True)):
        if not base.is_dir():
            continue
        for fp in sorted(base.glob("ratchet-*.json")):
            try:
                p = Proposal.from_dict(json.loads(fp.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, KeyError):
                continue
            if is_applied and p.status != "applied":
                p.status = "applied"
            if status is None or p.status == status:
                out.append(p)
    return out


def delete_pending_proposal(workspace: Path, proposal_id: str) -> None:
    p = proposal_path(workspace, proposal_id, applied=False)
    if p.is_file():
        p.unlink()


def reject_proposal(workspace: Path, proposal_id: str) -> bool:
    p = load_proposal(workspace, proposal_id)
    if not p or p.status != "pending":
        return False
    p.status = "rejected"
    delete_pending_proposal(workspace, proposal_id)
    save_proposal(workspace, p, applied=True)
    return True


def slug_safe(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", text)[:40].strip("-")
