"""Task-aware model routing from `.meris/settings.json` → `models`."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from meris.harness.settings import load_settings


def _entry_overrides(entry: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    if entry.get("provider"):
        out["provider"] = str(entry["provider"])
    if entry.get("model"):
        out["model"] = str(entry["model"])
    base = entry.get("baseUrl") or entry.get("base_url")
    if base:
        out["base_url"] = str(base)
    return out


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

    Priority: ``models.rules[]`` (first match) → ``models.byMode[mode]`` → ``models.default`` → env only.
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
                overrides = _entry_overrides(rule)
                if overrides:
                    label = rule.get("name") or f"rules[{i}]"
                    return overrides, label

    by_mode = models_cfg.get("byMode") or models_cfg.get("by_mode")
    if isinstance(by_mode, dict) and mode in by_mode:
        entry = by_mode[mode]
        if isinstance(entry, dict):
            overrides = _entry_overrides(entry)
            if overrides:
                return overrides, f"byMode:{mode}"

    default = models_cfg.get("default")
    if isinstance(default, dict):
        overrides = _entry_overrides(default)
        if overrides:
            return overrides, "default"

    return {}, ""
