"""Cluster session failures → actionable signatures (Self-Harness weakness mining)."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from meris.harness.ratchet.classify import (
    _harness_check_proposal,
    _plan_format_proposal,
    _stall_proposal,
    _workspace_proposal,
)
from meris.harness.ratchet.events import load_events
from meris.harness.ratchet.proposal import Proposal, list_proposals, save_proposal
from meris.harness.sessions import SessionRecord, list_sessions

_READ_TOOLS = frozenset({"read_file", "grep", "glob", "list_dir", "codegraph_search"})
_WRITE_TOOLS = frozenset({"write_file", "edit_file"})


@dataclass
class FailureCluster:
    signature: str
    label: str
    count: int
    sessions: list[str] = field(default_factory=list)
    sample: str = ""


def _tool_names(record: SessionRecord) -> list[str]:
    names: list[str] = []
    for msg in record.messages:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name = fn.get("name", "")
            if name:
                names.append(name)
    return names


def _session_signature(record: SessionRecord) -> str | None:
    status = record.status
    tools = _tool_names(record)
    reads = sum(1 for t in tools if t in _READ_TOOLS)
    writes = sum(1 for t in tools if t in _WRITE_TOOLS)

    if status == "max_turns":
        if reads >= 4 and writes == 0:
            return "stall_explore_no_write"
        return "stall_max_turns"
    if status == "dod_failed":
        return "dod_failed"
    if status == "error":
        return "error"
    if status == "denied":
        return "permission_denied"
    if status == "cancelled":
        return None
    return None


def _event_signature(ev: dict) -> str | None:
    kind = ev.get("kind", "")
    det = (ev.get("detail") or "").lower()
    if kind == "benchmark_fail" and "missing: [ ]" in det:
        return "plan_format"
    if kind in ("harness_check_fail", "dod_failed") and any(
        x in det for x in ("import:forge", "paths:readme", "harness check", "meris/readme")
    ):
        return "harness_check"
    if kind in ("permission_denied", "approve_denied"):
        return "permission_denied"
    if kind == "max_turns":
        return "stall_max_turns"
    if kind == "benchmark_fail" and "meris/readme" in det:
        return "path_cwd"
    return None


_SIGNATURE_LABELS: dict[str, str] = {
    "stall_max_turns": "Turn 用尽仍未完成",
    "stall_explore_no_write": "长时间探索、无写文件",
    "dod_failed": "DoD / 传感器验收失败",
    "harness_check": "Harness 静态检查失败",
    "plan_format": "Plan 缺少 `- [ ]` 格式",
    "permission_denied": "权限 / approve 拒绝",
    "path_cwd": "路径或 cwd 错误",
    "error": "运行错误",
}


def cluster_failures(
    workspace: Path,
    *,
    since_days: int = 14,
    min_count: int = 1,
) -> list[FailureCluster]:
    """Group recent failed sessions and ratchet events by failure signature."""
    ws = workspace.resolve()
    counts: Counter[str] = Counter()
    sessions_by_sig: dict[str, list[str]] = {}
    samples: dict[str, str] = {}

    for rec in list_sessions(ws):
        if rec.status in ("completed", "running"):
            continue
        sig = _session_signature(rec)
        if not sig:
            continue
        counts[sig] += 1
        sessions_by_sig.setdefault(sig, []).append(rec.id)
        if sig not in samples:
            samples[sig] = f"{rec.status} turn={rec.turn} task={rec.task[:80]}"

    for ev in load_events(ws, since_days=since_days):
        sig = _event_signature(ev)
        if not sig:
            continue
        counts[sig] += 1
        sid = ev.get("session", "")
        if sid:
            sessions_by_sig.setdefault(sig, [])
            if sid not in sessions_by_sig[sig]:
                sessions_by_sig[sig].append(sid)
        if sig not in samples:
            samples[sig] = (ev.get("detail") or ev.get("kind", ""))[:120]

    clusters: list[FailureCluster] = []
    for sig, n in counts.most_common():
        if n < min_count:
            continue
        clusters.append(
            FailureCluster(
                signature=sig,
                label=_SIGNATURE_LABELS.get(sig, sig),
                count=n,
                sessions=sessions_by_sig.get(sig, [])[:8],
                sample=samples.get(sig, ""),
            )
        )
    return clusters


def proposal_for_signature(signature: str, *, sample: str = "") -> Proposal | None:
    """Map cluster signature → ratchet proposal template."""
    fake_ev = {"kind": signature, "detail": sample, "task_id": "cluster"}
    if signature == "plan_format":
        fake_ev = {"kind": "benchmark_fail", "detail": "missing: [ ]", "task_id": "plan_smoke"}
        return _plan_format_proposal(fake_ev)
    if signature == "harness_check":
        fake_ev = {
            "kind": "harness_check_fail",
            "detail": sample or "harness check paths:readme",
        }
        return _harness_check_proposal(fake_ev)
    if signature in ("stall_max_turns", "stall_explore_no_write"):
        fake_ev = {"kind": "max_turns", "detail": sample or "max turns reached"}
        return _stall_proposal(fake_ev)
    if signature == "path_cwd":
        fake_ev = {"kind": "permission_denied", "detail": sample or "blocked meris/README"}
        return _workspace_proposal(fake_ev)
    return None


def propose_from_clusters(
    workspace: Path,
    clusters: list[FailureCluster],
    *,
    min_count: int = 2,
) -> list[Proposal]:
    """Create pending proposals for clusters that repeat (default ≥2)."""
    ws = workspace.resolve()
    pending = list_proposals(ws, status="pending")
    pending_lessons = {p.lesson for p in pending}
    saved: list[Proposal] = []

    for c in clusters:
        if c.count < min_count:
            continue
        p = proposal_for_signature(c.signature, sample=c.sample)
        if not p:
            continue
        if p.lesson in pending_lessons:
            continue
        p.signals = [f"cluster:{c.signature}"] + [f"session:{s}" for s in c.sessions[:3]]
        p.summary = f"[cluster×{c.count}] {p.summary}"
        save_proposal(ws, p)
        saved.append(p)
        pending_lessons.add(p.lesson)
    return saved
