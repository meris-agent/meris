"""Load `.meris/settings.yaml` (or legacy `.json`) with defaults."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from meris.harness.paths import harness_root

SHARED_SETTINGS_NAMES = ("settings.yaml", "settings.yml", "settings.json")
LOCAL_SETTINGS_NAMES = ("settings.local.yaml", "settings.local.yml", "settings.local.json")

DEFAULT_SETTINGS: dict = {
    "permissions": {
        "allow": [
            "Read",
            "Edit",
            "Write",
            "Glob",
            "Grep",
            "Git",
            "Bash(pytest*)",
            "Bash(python*)",
            "Bash(git status*)",
            "Bash(git diff*)",
            "Bash(git add*)",
            "MCP",
        ],
        "deny": ["Bash(rm -rf*)", "Bash(git push*)", "Bash(curl*)"],
    },
    "sensors": {
        "postEdit": [],
        "onComplete": True,
    },
    "context": {
        "maxMessages": 48,
        "maxTokens": 32000,
        "maxToolTokens": 2000,
    },
    "blockedPaths": ["**/generated/**", "**/node_modules/**"],
    "sandbox": {
        "mode": "warn",
        "bashTimeoutSec": 120,
        "osSandbox": "auto",
        "network": "shared",
        "maskSecrets": True,
    },
    "hooks": {
        "preToolUse": [],
        "postToolUse": [],
        "onSave": [],
        "onCommit": [],
    },
    "mcpServers": {},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, val in override.items():
        if key == "models" and isinstance(val, dict) and isinstance(out.get("models"), dict):
            out["models"] = _merge_models(out["models"], val)
        elif isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _merge_rules_by_name(base: list, override: list) -> list:
    """Merge routing rules by ``name`` — local overrides shared without replacing whole list."""
    named: dict[str, dict] = {}
    unnamed: list = []
    for item in base:
        if isinstance(item, dict) and item.get("name"):
            named[str(item["name"])] = dict(item)
        else:
            unnamed.append(item)
    for item in override:
        if isinstance(item, dict) and item.get("name"):
            key = str(item["name"])
            if key in named:
                named[key] = _deep_merge(named[key], item)
            else:
                named[key] = dict(item)
        else:
            unnamed.append(item)
    return unnamed + list(named.values())


def _merge_models(base: dict, override: dict) -> dict:
    out = _deep_merge({k: v for k, v in base.items() if k != "rules"}, {k: v for k, v in override.items() if k != "rules"})
    base_rules = base.get("rules")
    over_rules = override.get("rules")
    if isinstance(base_rules, list) and isinstance(over_rules, list):
        out["rules"] = _merge_rules_by_name(base_rules, over_rules)
    elif over_rules is not None:
        out["rules"] = over_rules
    elif base_rules is not None:
        out["rules"] = base_rules
    return out


def _load_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def _first_existing(hroot: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        p = hroot / name
        if p.is_file():
            return p
    return None


def shared_settings_path(hroot: Path) -> Path | None:
    return _first_existing(hroot, SHARED_SETTINGS_NAMES)


def local_settings_path(hroot: Path) -> Path | None:
    return _first_existing(hroot, LOCAL_SETTINGS_NAMES)


def shared_settings_relpath(workspace: Path) -> str:
    hroot = harness_root(workspace.resolve())
    p = shared_settings_path(hroot)
    if p is not None:
        return p.name
    return "settings.yaml"


def load_settings(workspace: Path) -> dict:
    """Load team settings, merged with optional gitignored local override."""
    hroot = harness_root(workspace.resolve())
    merged = dict(DEFAULT_SETTINGS)
    shared = shared_settings_path(hroot)
    if shared is not None:
        data = _load_file(shared)
        for key, val in data.items():
            if isinstance(val, dict) and isinstance(merged.get(key), dict):
                merged[key] = _deep_merge(merged[key], val)
            else:
                merged[key] = val
    local = local_settings_path(hroot)
    if local is not None:
        merged = _deep_merge(merged, _load_file(local))
    return merged
