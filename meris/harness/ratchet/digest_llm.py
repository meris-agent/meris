"""Optional LLM pass for ratchet digest."""

from __future__ import annotations

import json
from pathlib import Path

from meris.harness.ratchet.analyze import _extract_json_object
from meris.harness.ratchet.apply import is_allowed_target
from meris.harness.ratchet.digest import collect_user_messages
from meris.harness.ratchet.insights import Insight, new_insight_id
from meris.provider import Provider, ProviderError, get_provider

MAX_SNIPPETS = 40
MAX_SNIPPET_CHARS = 300


def build_digest_llm_prompt(workspace: Path, *, since_days: int = 30) -> str:
    pairs = collect_user_messages(workspace, since_days=since_days)
    snippets = [f"[{sid}] {text[:MAX_SNIPPET_CHARS]}" for sid, text in pairs[-MAX_SNIPPETS:]]
    body = "\n".join(snippets) if snippets else "(no user messages)"

    return f"""From Meris agent **user messages** (not assistant), infer repeated **user habits or project preferences**
worth saving in Harness (.meris/rules or .meris/skills only).

## User messages (recent)
{body}

## Output
Respond with ONLY JSON:
{{
  "insights": [
    {{
      "kind": "user_habit|project_preference",
      "pattern": "one line summary",
      "question": "question to ask the user before writing harness",
      "lesson": "L-insight-short-slug",
      "target": ".meris/rules/user-prefs.md",
      "content": "markdown with <!-- ratchet:LESSON --> as first line"
    }}
  ]
}}
- Max 3 insights. Only themes mentioned in **2+ distinct sessions** (infer from session ids).
- Do NOT include API keys or private paths.
- Do NOT patch Python source.
"""


def insights_from_llm_payload(data: dict, *, existing_lessons: set[str]) -> list[Insight]:
    raw = data.get("insights") or []
    if not isinstance(raw, list):
        return []
    out: list[Insight] = []
    for item in raw[:3]:
        if not isinstance(item, dict):
            continue
        lesson = str(item.get("lesson", "L-insight-llm"))[:40]
        if lesson in existing_lessons:
            continue
        path = str(item.get("target", ".meris/rules/user-prefs.md")).replace("\\", "/")
        if not is_allowed_target(path):
            continue
        content = str(item.get("content", ""))[:4000]
        if f"<!-- ratchet:{lesson} -->" not in content:
            content = f"<!-- ratchet:{lesson} -->\n\n{content.lstrip()}"
        out.append(
            Insight(
                id=new_insight_id(),
                kind=str(item.get("kind", "user_habit")),
                pattern=str(item.get("pattern", ""))[:200],
                question=str(item.get("question", "Apply this habit to Harness?"))[:300],
                count=2,
                evidence=["llm:inferred"],
                suggested_target=path,
                suggested_content=content,
                lesson=lesson,
                status="pending",
                source="llm",
            )
        )
        existing_lessons.add(lesson)
    return out


async def digest_sessions_llm(
    workspace: Path,
    *,
    since_days: int = 30,
    existing: list[Insight] | None = None,
    provider: Provider | None = None,
) -> list[Insight]:
    ws = workspace.resolve()
    existing = existing or []
    lessons = {i.lesson for i in existing}
    prompt = build_digest_llm_prompt(ws, since_days=since_days)
    prov = provider or get_provider()
    try:
        text = await prov.complete(prompt, system="You output strict JSON only.")
    except ProviderError:
        return []
    data = _extract_json_object(text)
    if not data:
        return []
    return insights_from_llm_payload(data, existing_lessons=lessons)
