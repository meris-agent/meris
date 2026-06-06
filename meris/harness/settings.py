"""Load `.meris/settings.json` with defaults."""

from __future__ import annotations

import json
from pathlib import Path

from meris.harness.paths import harness_root

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
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_settings(workspace: Path) -> dict:
    """Load settings.json, merged with optional gitignored settings.local.json."""
    hroot = harness_root(workspace)
    merged = dict(DEFAULT_SETTINGS)
    data = _load_json(hroot / "settings.json")
    for key, val in data.items():
        if isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    local = _load_json(hroot / "settings.local.json")
    if local:
        merged = _deep_merge(merged, local)
    return merged
