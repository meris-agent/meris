"""Harness entropy scan — read-mostly health checks for `.meris/` and docs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from meris.harness.paths import harness_root
from meris.harness.ratchet.proposal import list_proposals

_AGENTS_DOD = re.compile(r"pytest tests/.*-m.*not integration", re.I)
_TESTING_DOD = re.compile(r"pytest tests/.*-m.*not integration", re.I)
_SESSION_NOTE = re.compile(r"^## Session note \(", re.M)
_RATchet_MARKER = re.compile(r"<!-- ratchet:")


@dataclass
class GcFinding:
    id: str
    severity: str  # info | warn | fail
    detail: str
    hint: str = ""


def _file_age_days(path: Path) -> float | None:
    if not path.is_file():
        return None
    mtime = path.stat().st_mtime
    return (datetime.now(timezone.utc).timestamp() - mtime) / 86400


def run_harness_gc(workspace: Path) -> list[GcFinding]:
    """Scan harness health; does not modify files."""
    ws = workspace.resolve()
    findings: list[GcFinding] = []

    agents = ws / "AGENTS.md"
    if agents.is_file():
        text = agents.read_text(encoding="utf-8", errors="replace")
        if len(text) > 8000:
            findings.append(
                GcFinding(
                    "agents-size",
                    "warn",
                    f"AGENTS.md is {len(text)} chars — consider linking to docs/harness/",
                    hint="Keep AGENTS.md as a map, not an encyclopedia",
                )
            )

    progress = ws / "PROGRESS.md"
    if progress.is_file():
        ptext = progress.read_text(encoding="utf-8", errors="replace")
        age = _file_age_days(progress)
        if age is not None and age > 30 and not _SESSION_NOTE.search(ptext):
            findings.append(
                GcFinding(
                    "progress-stale",
                    "warn",
                    f"PROGRESS.md not updated in {int(age)} days and has no session notes",
                    hint="Append a session note or trim stale blocks",
                )
            )
        if ptext.count("## Ratchet 摘要") > 1:
            findings.append(
                GcFinding(
                    "progress-dup-summary",
                    "warn",
                    "Multiple Ratchet summary sections in PROGRESS.md",
                    hint="Merge into one ## Ratchet 摘要 block",
                )
            )

    testing = ws / "docs" / "harness" / "testing.md"
    if agents.is_file() and testing.is_file():
        a_dod = _AGENTS_DOD.search(agents.read_text(encoding="utf-8", errors="replace"))
        t_dod = _TESTING_DOD.search(testing.read_text(encoding="utf-8", errors="replace"))
        if a_dod and t_dod and a_dod.group(0) != t_dod.group(0):
            findings.append(
                GcFinding(
                    "doc-drift-dod",
                    "warn",
                    "AGENTS.md DoD pytest command differs from docs/harness/testing.md",
                    hint="Align Definition of Done across AGENTS.md and testing.md",
                )
            )

    hroot = harness_root(ws)
    for sub, label in (("rules", "rules"), ("skills", "skills")):
        d = hroot / sub
        if not d.is_dir():
            continue
        files = list(d.glob("*.md"))
        if len(files) > 20:
            findings.append(
                GcFinding(
                    f"{label}-count",
                    "warn",
                    f"{len(files)} {label} files — context and maintenance cost rising",
                    hint=f"Archive or merge unused .meris/{sub}/ entries",
                )
            )
        for fp in files:
            text = fp.read_text(encoding="utf-8", errors="replace")
            markers = _RATchet_MARKER.findall(text)
            lessons = {m for m in re.findall(r"ratchet:([A-Za-z0-9_-]+)", text)}
            if len(markers) > len(lessons) + 2:
                findings.append(
                    GcFinding(
                        f"dup-ratchet-{fp.name}",
                        "info",
                        f"{fp.relative_to(ws)} has repeated ratchet markers",
                        hint="Deduplicate ratchet blocks in this file",
                    )
                )

    pending = list_proposals(ws, status="pending")
    if len(pending) > 10:
        findings.append(
            GcFinding(
                "ratchet-backlog",
                "warn",
                f"{len(pending)} pending ratchet proposals",
                hint="Run: meris ratchet review",
            )
        )

    events = hroot / "ratchet" / "events.jsonl"
    if events.is_file() and events.stat().st_size > 500_000:
        findings.append(
            GcFinding(
                "events-large",
                "info",
                f"ratchet/events.jsonl is {events.stat().st_size // 1024} KiB",
                hint="Archive old events or rotate the file",
            )
        )

    if not findings:
        findings.append(GcFinding("ok", "info", "No harness entropy issues detected"))
    return findings


def gc_has_warnings(findings: list[GcFinding]) -> bool:
    return any(f.severity in ("warn", "fail") for f in findings if f.id != "ok")
