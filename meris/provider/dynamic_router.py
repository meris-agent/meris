"""LLM-based per-turn model routing (opt-in via ``models.dynamic``)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from meris.provider.factory import get_provider
from meris.provider.profiles import (
    build_candidate_catalog,
    build_profiles_catalog,
    entry_overrides,
    mode_default_profile,
    mode_strategy,
    resolve_profile,
)
from meris.provider.router import resolve_rule_routing, resolve_task_routing

_MUTATING_TOOLS = frozenset({"write_file", "edit_file", "bash", "git_commit"})


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


def build_profile_catalog(models_cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Backward-compatible alias for full profile catalog."""
    return build_profiles_catalog(models_cfg)


def _static_fallback(
    workspace: Path,
    mode: str,
    task: str,
    models_cfg: dict[str, Any],
) -> tuple[dict[str, str], str, str]:
    overrides, note = resolve_task_routing(workspace, mode, task)
    if overrides:
        return overrides, note or "static", ""
    default_name = mode_default_profile(models_cfg, mode)
    overrides = resolve_profile(models_cfg, default_name)
    if overrides:
        return overrides, f"profile:{default_name}", ""
    return {}, "", ""


def _profile_overrides(catalog: dict[str, dict[str, Any]], profile_id: str) -> dict[str, str] | None:
    entry = catalog.get(profile_id)
    if not entry:
        return None
    overrides = entry_overrides(entry)
    return overrides or None


def _summarize_context(mode: str, task: str, turn: int, messages: list[dict[str, Any]]) -> str:
    lines = [f"mode={mode}", f"turn={turn}", f"task={task[:600]}"]
    for msg in messages[-8:]:
        role = msg.get("role")
        if role == "assistant" and msg.get("tool_calls"):
            names = [tc.get("function", {}).get("name", "?") for tc in msg["tool_calls"]]
            lines.append(f"assistant tools: {', '.join(names)}")
        elif role in ("user", "assistant"):
            content = (msg.get("content") or "").strip()
            if content:
                lines.append(f"{role}: {content[:400]}")
    return "\n".join(lines)


def _needs_reroute(messages: list[dict[str, Any]], turn: int) -> bool:
    if turn <= 1:
        return True
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            name = tc.get("function", {}).get("name", "")
            if name in _MUTATING_TOOLS:
                return True
        break
    return False


def _format_profiles_for_prompt(catalog: dict[str, dict[str, Any]]) -> str:
    lines: list[str] = []
    for pid, entry in catalog.items():
        hint = entry.get("hint") or ""
        model = entry.get("model") or "?"
        provider = entry.get("provider") or "?"
        lines.append(f"- {pid}: {provider}/{model} — {hint}")
    return "\n".join(lines)


def _build_router_messages(
    mode: str,
    task: str,
    turn: int,
    messages: list[dict[str, Any]],
    catalog: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    profiles = _format_profiles_for_prompt(catalog)
    system = (
        "You are a model router for a coding agent. Pick exactly ONE profile id for the next turn.\n"
        "Prefer the cheapest profile that is sufficient. Escalate for multi-file edits, refactors, or hard bugs.\n"
        "Reply with JSON only: {\"profile\": \"<id>\", \"reason\": \"<short>\"}\n\n"
        f"Profiles:\n{profiles}"
    )
    user = _summarize_context(mode, task, turn, messages)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _dynamic_enabled(models_cfg: dict[str, Any]) -> bool:
    dynamic = models_cfg.get("dynamic")
    return isinstance(dynamic, dict) and bool(dynamic.get("enabled"))


async def pick_model_for_turn(
    workspace: Path,
    *,
    mode: str,
    task: str,
    turn: int,
    messages: list[dict[str, Any]],
    models_cfg: dict[str, Any],
    last_overrides: dict[str, str] | None = None,
) -> tuple[dict[str, str], str, str]:
    """
    Pick provider overrides for this agent turn.

    Static modes use ``profile`` bindings; dynamic modes call ``models.dynamic.router``.
    Rules always win before dynamic selection.
    """
    ws = workspace.resolve()

    rule_overrides, rule_note = resolve_rule_routing(models_cfg, mode, task)
    if rule_overrides:
        return rule_overrides, rule_note, "rule"

    if not _dynamic_enabled(models_cfg) or mode_strategy(models_cfg, mode) != "dynamic":
        return _static_fallback(ws, mode, task, models_cfg)

    catalog = build_candidate_catalog(models_cfg, mode)
    if not catalog:
        return _static_fallback(ws, mode, task, models_cfg)
    if len(catalog) == 1:
        only_id = next(iter(catalog))
        return entry_overrides(catalog[only_id]), f"profile:{only_id}", "single candidate"

    dynamic = models_cfg["dynamic"]
    re_route = str(dynamic.get("reRoute") or dynamic.get("re_route") or "everyTurn")
    if re_route == "onMutation" and last_overrides and not _needs_reroute(messages, turn):
        pid = _match_profile_id(last_overrides, catalog) or "cached"
        return last_overrides, f"profile:{pid}", "cached"

    router_cfg = dynamic.get("router") or dynamic.get("classifier") or {}
    if not isinstance(router_cfg, dict) or not router_cfg.get("provider"):
        return _static_fallback(ws, mode, task, models_cfg)

    router = get_provider(
        provider=str(router_cfg.get("provider")),
        model=str(router_cfg.get("model") or ""),
        base_url=router_cfg.get("baseUrl") or router_cfg.get("base_url"),
    )
    router_msgs = _build_router_messages(mode, task, turn, messages, catalog)
    try:
        reply = await router.chat(router_msgs)
    except Exception:
        return _static_fallback(ws, mode, task, models_cfg)

    parsed = _extract_json_object(reply.get("content") or "")
    profile_id = str((parsed or {}).get("profile") or "").strip()
    reason = str((parsed or {}).get("reason") or "").strip()
    overrides = _profile_overrides(catalog, profile_id)
    if not overrides:
        default_id = mode_default_profile(models_cfg, mode)
        overrides = _profile_overrides(catalog, default_id)
        if not overrides:
            return _static_fallback(ws, mode, task, models_cfg)
        profile_id = default_id
        reason = reason or "router fallback"

    return overrides, f"dynamic:{profile_id}", reason


def _match_profile_id(overrides: dict[str, str], catalog: dict[str, dict[str, Any]]) -> str | None:
    for pid, entry in catalog.items():
        eo = entry_overrides(entry)
        if eo.get("provider") == overrides.get("provider") and eo.get("model") == overrides.get("model"):
            return pid
    return None
