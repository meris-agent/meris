"""LLM-assisted ratchet analysis → JSON proposals."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from meris.harness.ratchet.apply import is_allowed_target
from meris.harness.ratchet.events import load_events
from meris.harness.ratchet.profile import load_profile_text
from meris.harness.ratchet.proposal import (
    Proposal,
    ProposalTarget,
    new_proposal_id,
    save_proposal,
)
from meris.harness.sessions import SessionRecord, list_sessions, load_session
from meris.provider import Provider, ProviderError, get_provider

MAX_CONTENT_CHARS = 4000
ALLOWED_ANALYZE_PREFIXES = (".meris/rules/", ".meris/skills/")


def _session_excerpt(record: SessionRecord, *, max_messages: int = 8) -> str:
    lines: list[str] = []
    lines.append(f"session={record.id} status={record.status} mode={record.mode}")
    lines.append(f"task: {record.task[:500]}")
    for msg in record.messages[-max_messages:]:
        role = msg.get("role", "?")
        content = (msg.get("content") or "")[:800]
        if content:
            lines.append(f"[{role}] {content}")
        if msg.get("tool_calls"):
            lines.append(f"[{role}] tool_calls={len(msg['tool_calls'])}")
    return "\n".join(lines)


def resolve_analyze_session(
    workspace: Path,
    *,
    session_id: str | None = None,
    last_fail: bool = False,
) -> SessionRecord | None:
    ws = workspace.resolve()
    if session_id:
        return load_session(ws, session_id)
    if last_fail:
        for rec in list_sessions(ws):
            if rec.status in ("dod_failed", "error", "denied"):
                return rec
        events = load_events(ws, since_days=14)
        for ev in reversed(events):
            if ev.get("kind") in ("benchmark_fail", "dod_failed", "error"):
                sid = ev.get("session", "")
                if sid:
                    return load_session(ws, sid)
    sessions = list_sessions(ws)
    return sessions[0] if sessions else None


def build_analyze_prompt(
    workspace: Path,
    *,
    session: SessionRecord | None = None,
    since_days: int = 14,
) -> str:
    from meris.harness.guides import load_guides

    ws = workspace.resolve()
    events = load_events(ws, since_days=since_days)[-30:]
    events_text = json.dumps(events, ensure_ascii=False, indent=2)[:6000]
    guides = load_guides(ws)[:4000]
    profile = load_profile_text(ws)
    session_text = _session_excerpt(session) if session else "(no session)"

    return f"""Analyze why the Meris agent struggled and propose harness file patches.

## Ratchet events (recent)
{events_text}

## Session excerpt
{session_text}

## Existing harness (guides + rules)
{guides}

## User profile
{profile or "(none)"}

## Output rules
- Respond with ONLY a JSON object, no markdown outside JSON.
- Schema:
{{
  "proposals": [
    {{
      "lesson": "L-analyze-short-id",
      "summary": "one line",
      "confidence": "high|medium|low",
      "target": {{
        "path": ".meris/rules/example.md or .meris/skills/example.md",
        "action": "append|create",
        "content": "markdown to append (include <!-- ratchet:LESSON --> as first line)"
      }},
      "verify": ["optional shell command"]
    }}
  ]
}}
- Max 3 proposals. Only paths under `.meris/rules/` or `.meris/skills/`.
- Do NOT patch Python source. Prefer short, actionable rules.
- Examples in content MUST use file paths from **Existing harness** (AGENTS.md, paths.md).
- Content max {MAX_CONTENT_CHARS} chars per proposal.
"""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _validate_target_path(path: str) -> bool:
    norm = path.replace("\\", "/")
    if norm == "AGENTS.md":
        return True
    if any(norm.startswith(p) for p in ALLOWED_ANALYZE_PREFIXES):
        return True
    return is_allowed_target(norm, force_agents=False)


def proposals_from_llm_payload(
    data: dict[str, Any],
    *,
    signal: str = "analyze:llm",
) -> list[Proposal]:
    raw = data.get("proposals") or []
    if not isinstance(raw, list):
        return []

    out: list[Proposal] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        t = item.get("target") or {}
        path = str(t.get("path", "")).replace("\\", "/")
        if not path or not _validate_target_path(path):
            continue
        content = str(t.get("content", ""))[:MAX_CONTENT_CHARS]
        lesson = str(item.get("lesson", "L-analyze"))[:40]
        if "<!-- ratchet:" not in content:
            content = f"<!-- ratchet:{lesson} -->\n\n{content}"
        out.append(
            Proposal(
                id=new_proposal_id(),
                lesson=lesson,
                summary=str(item.get("summary", "LLM proposal"))[:200],
                target=ProposalTarget(
                    path=path,
                    action=str(t.get("action", "append")),
                    content=content,
                ),
                confidence=str(item.get("confidence", "medium")),
                signals=[signal],
                verify=[str(v) for v in (item.get("verify") or []) if isinstance(v, str)][:5],
            )
        )
    return out


async def analyze_workspace(
    workspace: Path,
    *,
    session_id: str | None = None,
    last_fail: bool = False,
    provider: Provider | None = None,
    save: bool = True,
    since_days: int = 14,
) -> list[Proposal]:
    """Call LLM to draft proposals from events + optional session."""
    ws = workspace.resolve()
    session = resolve_analyze_session(ws, session_id=session_id, last_fail=last_fail)
    prompt = build_analyze_prompt(ws, session=session, since_days=since_days)

    provider = provider or get_provider()
    msg = await provider.chat(
        [
            {
                "role": "system",
                "content": "You output strict JSON only for Meris harness ratchet proposals.",
            },
            {"role": "user", "content": prompt},
        ]
    )
    text = msg.get("content") or ""
    data = _extract_json_object(text)
    if not data:
        raise ProviderError(f"Could not parse JSON from model response: {text[:300]}")

    proposals = proposals_from_llm_payload(data)
    if save:
        for p in proposals:
            save_proposal(ws, p)
    return proposals
