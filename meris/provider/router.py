"""Task-aware model routing from `.meris/settings.json` → `models`."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from meris.harness.settings import load_settings
from meris.provider.profiles import (
    entry_overrides,
    get_mode_entry,
    mode_default_profile,
    mode_strategy,
    resolve_binding_overrides,
    resolve_profile,
)


def _entry_overrides(entry: dict[str, Any]) -> dict[str, str]:
    """Backward-compatible alias."""
    return entry_overrides(entry)


def _rule_matches(match: dict[str, Any], mode: str, task: str) -> bool:
    if match.get("mode") and match["mode"] != mode:
        return False
    needles = match.get("taskContains") or match.get("task_contains")
    if needles is not None:
        if isinstance(needles, str):
            needles = [needles]
        low = task.lower()
        if not any(str(n).lower() in low for n in needles):
            return False
    pattern = match.get("taskRegex") or match.get("task_regex")
    if pattern and not re.search(pattern, task, re.IGNORECASE):
        return False
    return True


def resolve_task_routing(
    workspace: Path,
    mode: str,
    task: str,
) -> tuple[dict[str, str], str]:
    """
    Return (get_provider kwargs overrides, human note).

    Priority: ``models.rules[]`` (first match) → static ``byMode[mode]`` → ``models.default`` → env only.
    Modes with ``strategy: dynamic`` fall back to ``defaultProfile`` / first candidate when dynamic routing is off.
    """
    settings = load_settings(workspace.resolve())
    models_cfg = settings.get("models")
    if not isinstance(models_cfg, dict) or not models_cfg:
        return {}, ""

    rules = models_cfg.get("rules")
    if isinstance(rules, list):
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            match = rule.get("match") or rule.get("when") or {}
            if isinstance(match, dict) and _rule_matches(match, mode, task):
                overrides = resolve_binding_overrides(models_cfg, rule, mode=mode)
                if not overrides and rule.get("provider"):
                    overrides = entry_overrides(rule)
                if overrides:
                    label = rule.get("name") or f"rules[{i}]"
                    if rule.get("profile"):
                        label = f"{label}:{rule['profile']}"
                    return overrides, label

    entry = get_mode_entry(models_cfg, mode)
    if entry:
        if mode_strategy(models_cfg, mode) == "dynamic":
            overrides = resolve_profile(models_cfg, mode_default_profile(models_cfg, mode))
            if overrides:
                return overrides, f"byMode:{mode}"
        else:
            overrides = resolve_binding_overrides(models_cfg, entry, mode=mode)
            if overrides:
                profile = entry.get("profile")
                note = f"byMode:{mode}:{profile}" if profile else f"byMode:{mode}"
                return overrides, note

    default = models_cfg.get("default")
    if isinstance(default, dict):
        overrides = resolve_binding_overrides(models_cfg, default, mode=mode)
        if not overrides and default.get("provider"):
            overrides = entry_overrides(default)
        if overrides:
            return overrides, "default"

    return {}, ""


def resolve_rule_routing(
    models_cfg: dict[str, Any],
    mode: str,
    task: str,
) -> tuple[dict[str, str], str]:
    """Rules-only routing (used before dynamic per-turn selection)."""
    rules = models_cfg.get("rules")
    if not isinstance(rules, list):
        return {}, ""
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        match = rule.get("match") or rule.get("when") or {}
        if isinstance(match, dict) and _rule_matches(match, mode, task):
            overrides = resolve_binding_overrides(models_cfg, rule, mode=mode)
            if not overrides and rule.get("provider"):
                overrides = entry_overrides(rule)
            if overrides:
                label = rule.get("name") or f"rules[{i}]"
                if rule.get("profile"):
                    label = f"{label}:{rule['profile']}"
                return overrides, label
    return {}, ""
