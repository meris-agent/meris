"""Pytest bootstrap — reload User-level env on Windows."""

from __future__ import annotations

import os
import sys

import pytest

from meris.env import load_env

# Refresh stale process env from User registry (Windows Cursor terminals)
if sys.platform == "win32":
    for name in (
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "MERIS_BASE_URL",
        "MERIS_MODEL",
        "FORGE_BASE_URL",
        "FORGE_MODEL",
        "OPENAI_API_KEY",
    ):
        val = os.environ.get(name) or ""
        # If missing or looks like old invalid key placeholder, try User scope
        try:
            import winreg  # type: ignore

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                user_val, _ = winreg.QueryValueEx(k, name)
                if user_val and user_val != val:
                    os.environ[name] = user_val
        except OSError:
            pass

load_env()


@pytest.fixture
def workspace(tmp_path):
    import json
    from pathlib import Path

    ws: Path = tmp_path
    (ws / "AGENTS.md").write_text(
        "# AGENTS\n\n## Definition of Done\n\n- `python -c \"print(0)\"`\n",
        encoding="utf-8",
    )
    (ws / "hello.py").write_text("print('hello')\n", encoding="utf-8")
    harness = ws / ".meris"
    harness.mkdir()
    (harness / "settings.json").write_text(
        json.dumps({"permissions": {"deny": ["Bash(rm -rf*)"]}}),
        encoding="utf-8",
    )
    return ws
