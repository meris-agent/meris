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


def load_settings(workspace: Path) -> dict:
    p = harness_root(workspace) / "settings.json"
    if not p.is_file():
        return dict(DEFAULT_SETTINGS)
    data = json.loads(p.read_text(encoding="utf-8"))
    merged = dict(DEFAULT_SETTINGS)
    for key, val in data.items():
        if isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **val}
        else:
            merged[key] = val
    return merged
