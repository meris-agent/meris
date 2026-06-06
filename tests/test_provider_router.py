"""Task-based model routing from settings."""

from __future__ import annotations

import json

import pytest

from meris.harness.paths import HARNESS_DIR
from meris.provider.router import resolve_task_routing


def _write_models(workspace, models: dict) -> None:
    h = workspace / HARNESS_DIR
    h.mkdir(parents=True, exist_ok=True)
    settings_path = h / "settings.json"
    data = {}
    if settings_path.is_file():
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    data["models"] = models
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_route_by_mode(workspace) -> None:
    _write_models(
        workspace,
        {
            "byMode": {
                "ask": {"provider": "openai", "model": "gpt-4o-mini"},
                "run": {"provider": "deepseek", "model": "deepseek-chat"},
            }
        },
    )
    overrides, note = resolve_task_routing(workspace, "ask", "where is auth?")
    assert overrides["provider"] == "openai"
    assert note == "byMode:ask"


def test_route_rules_before_by_mode(workspace) -> None:
    _write_models(
        workspace,
        {
            "profiles": {
                "chat": {"provider": "deepseek", "model": "deepseek-chat"},
                "strong": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
            },
            "byMode": {"run": {"profile": "chat"}},
            "rules": [
                {
                    "name": "refactor",
                    "match": {"mode": "run", "taskContains": ["重构"]},
                    "profile": "strong",
                }
            ],
        },
    )
    overrides, note = resolve_task_routing(workspace, "run", "大规模重构模块")
    assert overrides["provider"] == "anthropic"
    assert note == "refactor:strong"


def test_route_by_profile(workspace) -> None:
    _write_models(
        workspace,
        {
            "profiles": {
                "fast": {"provider": "openai", "model": "gpt-4o-mini"},
            },
            "byMode": {"ask": {"profile": "fast"}},
        },
    )
    overrides, note = resolve_task_routing(workspace, "ask", "where is auth?")
    assert overrides["provider"] == "openai"
    assert note == "byMode:ask:fast"


def test_no_models_config(workspace) -> None:
    overrides, note = resolve_task_routing(workspace, "run", "anything")
    assert overrides == {}
    assert note == ""
