"""Model profiles and mode binding resolution for ``models`` settings."""

from __future__ import annotations

from typing import Any

_DEFAULT_HINTS: dict[str, str] = {
    "ask": "只读问答、查位置、解释代码",
    "plan": "写计划、拆任务、不改仓库",
    "run": "改代码、跑命令、实现功能",
}


def entry_overrides(entry: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    if entry.get("provider"):
        out["provider"] = str(entry["provider"])
    if entry.get("model"):
        out["model"] = str(entry["model"])
    base = entry.get("baseUrl") or entry.get("base_url")
    if base:
        out["base_url"] = str(base)
    return out


def _by_mode_map(models_cfg: dict[str, Any]) -> dict[str, Any]:
    raw = models_cfg.get("byMode") or models_cfg.get("by_mode")
    return raw if isinstance(raw, dict) else {}


def build_profiles_catalog(models_cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """All defined profiles (explicit ``profiles`` + legacy inline entries)."""
    explicit = models_cfg.get("profiles")
    if isinstance(explicit, dict) and explicit:
        out: dict[str, dict[str, Any]] = {}
        for name, entry in explicit.items():
            if isinstance(entry, dict) and entry.get("provider"):
                out[str(name)] = dict(entry)
        return out

    out: dict[str, dict[str, Any]] = {}
    for mode_name, entry in _by_mode_map(models_cfg).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("provider"):
            prof = dict(entry)
            prof.setdefault("hint", _DEFAULT_HINTS.get(str(mode_name), str(mode_name)))
            out[str(mode_name)] = prof

    rules = models_cfg.get("rules")
    if isinstance(rules, list):
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            if rule.get("provider"):
                name = str(rule.get("name") or f"rule-{i}")
                prof = entry_overrides(rule)
                prof["hint"] = str(rule.get("hint") or rule.get("summary") or name)
                out[name] = prof

    default = models_cfg.get("default")
    if isinstance(default, dict) and default.get("provider"):
        out.setdefault(
            "default",
            {**default, "hint": default.get("hint") or "fallback default"},
        )
    return out


def resolve_profile(models_cfg: dict[str, Any], profile_id: str) -> dict[str, str]:
    catalog = build_profiles_catalog(models_cfg)
    entry = catalog.get(profile_id)
    if not entry:
        return {}
    return entry_overrides(entry)


def get_mode_entry(models_cfg: dict[str, Any], mode: str) -> dict[str, Any] | None:
    entry = _by_mode_map(models_cfg).get(mode)
    return entry if isinstance(entry, dict) else None


def mode_strategy(models_cfg: dict[str, Any], mode: str) -> str:
    entry = get_mode_entry(models_cfg, mode)
    if not entry:
        return "static"
    strategy = entry.get("strategy") or entry.get("route")
    if strategy in ("dynamic", "llm"):
        return "dynamic"
    if entry.get("candidates"):
        return "dynamic"
    return "static"


def mode_candidates(models_cfg: dict[str, Any], mode: str) -> list[str]:
    entry = get_mode_entry(models_cfg, mode) or {}
    raw = entry.get("candidates") or entry.get("profiles") or []
    if isinstance(raw, str):
        raw = [raw]
    ids = [str(x) for x in raw if x]
    if ids:
        return ids
    profile = entry.get("profile") or entry.get("defaultProfile")
    if profile:
        return [str(profile)]
    if entry.get("provider"):
        return [mode]
    catalog = build_profiles_catalog(models_cfg)
    return list(catalog.keys())


def mode_default_profile(models_cfg: dict[str, Any], mode: str) -> str:
    entry = get_mode_entry(models_cfg, mode) or {}
    for key in ("defaultProfile", "default_profile", "profile"):
        val = entry.get(key)
        if val:
            return str(val)
    dynamic = models_cfg.get("dynamic") if isinstance(models_cfg.get("dynamic"), dict) else {}
    global_default = dynamic.get("defaultProfile") or dynamic.get("default_profile")
    if global_default:
        return str(global_default)
    candidates = mode_candidates(models_cfg, mode)
    if candidates:
        return candidates[0]
    return mode


def build_candidate_catalog(
    models_cfg: dict[str, Any],
    mode: str,
) -> dict[str, dict[str, Any]]:
    """Profile subset available for dynamic routing in this mode."""
    all_profiles = build_profiles_catalog(models_cfg)
    if not all_profiles:
        return {}
    ids = mode_candidates(models_cfg, mode)
    if not ids:
        return all_profiles
    out: dict[str, dict[str, Any]] = {}
    for pid in ids:
        if pid in all_profiles:
            out[pid] = all_profiles[pid]
        elif pid == mode and mode in all_profiles:
            out[pid] = all_profiles[pid]
    return out or all_profiles


def resolve_binding_overrides(
    models_cfg: dict[str, Any],
    binding: dict[str, Any],
    *,
    mode: str = "",
) -> dict[str, str]:
    """Resolve a rule or byMode entry to provider overrides."""
    profile_id = binding.get("profile")
    if profile_id:
        overrides = resolve_profile(models_cfg, str(profile_id))
        if overrides:
            return overrides
    if binding.get("provider"):
        return entry_overrides(binding)
    if mode_strategy(models_cfg, mode) == "dynamic":
        return resolve_profile(models_cfg, mode_default_profile(models_cfg, mode))
    return {}
