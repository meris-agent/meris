"""Context compression — message count + token budget."""

from __future__ import annotations

import json
from typing import Any

# Rough heuristic when tiktoken unavailable (~4 chars/token English/code mix)
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    total = 0
    for m in messages:
        total += estimate_tokens(str(m.get("content") or ""))
        if m.get("tool_calls"):
            total += estimate_tokens(json.dumps(m["tool_calls"], ensure_ascii=False))
    return total


def truncate_content(text: str, max_tokens: int) -> str:
    budget_chars = max_tokens * CHARS_PER_TOKEN
    if len(text) <= budget_chars:
        return text
    keep = budget_chars - 40
    return text[:keep] + "\n...[meris: truncated for token budget]"


def shrink_tool_results(messages: list[dict[str, Any]], *, max_tool_tokens: int = 2000) -> list[dict[str, Any]]:
    """Truncate oversized tool role messages in-place copy."""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.get("role") == "tool":
            content = str(m.get("content") or "")
            if estimate_tokens(content) > max_tool_tokens:
                m = {**m, "content": truncate_content(content, max_tool_tokens)}
        out.append(m)
    return out


def compress_messages(
    messages: list[dict[str, Any]],
    *,
    max_messages: int = 48,
    max_tokens: int | None = None,
    max_tool_tokens: int = 2000,
) -> list[dict[str, Any]]:
    """Drop oldest turns; optionally enforce token budget."""
    msgs = shrink_tool_results(messages, max_tool_tokens=max_tool_tokens)

    if max_tokens is not None and estimate_messages_tokens(msgs) > max_tokens:
        msgs = _compress_by_tokens(msgs, max_tokens)

    if len(msgs) <= max_messages:
        return msgs

    system = [m for m in msgs if m.get("role") == "system"]
    rest = [m for m in msgs if m.get("role") != "system"]
    if not rest:
        return msgs

    first_user = 0
    for i, m in enumerate(rest):
        if m.get("role") == "user":
            first_user = i
            break

    head = rest[: first_user + 1]
    budget = max_messages - len(system) - len(head) - 1
    if budget < 4:
        budget = 4
    tail = rest[-budget:] if budget > 0 else []

    dropped = len(rest) - len(head) - len(tail)
    marker = {
        "role": "system",
        "content": f"[meris] Context compressed: dropped {dropped} older messages.",
    }
    return system + head + [marker] + tail


def _compress_by_tokens(messages: list[dict[str, Any]], max_tokens: int) -> list[dict[str, Any]]:
    """Keep system + first user task + newest messages within token budget."""
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    if not rest:
        return messages

    first_user_idx = 0
    for i, m in enumerate(rest):
        if m.get("role") == "user":
            first_user_idx = i
            break
    head = rest[: first_user_idx + 1]

    fixed = system + head
    fixed_tokens = estimate_messages_tokens(fixed)
    budget = max_tokens - fixed_tokens - estimate_tokens("[meris] token budget marker")
    if budget < 500:
        budget = 500

    tail: list[dict[str, Any]] = []
    used = 0
    for m in reversed(rest[first_user_idx + 1 :]):
        t = estimate_messages_tokens([m])
        if used + t > budget and tail:
            break
        tail.insert(0, m)
        used += t

    marker = {
        "role": "system",
        "content": (
            f"[meris] Token budget: kept ~{fixed_tokens + used} tokens "
            f"(limit {max_tokens}), dropped older turns."
        ),
    }
    return fixed + [marker] + tail
