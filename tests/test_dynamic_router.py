"""Dynamic LLM model routing."""

from __future__ import annotations

import json

import pytest

from meris.harness.paths import HARNESS_DIR
from meris.provider.dynamic_router import (
    _needs_reroute,
    build_profile_catalog,
    pick_model_for_turn,
)

_PROFILES_CFG = {
    "profiles": {
        "fast": {"provider": "openai", "model": "gpt-4o-mini", "hint": "cheap"},
        "code": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "hint": "strong"},
    },
    "byMode": {
        "ask": {"profile": "fast"},
        "run": {
            "strategy": "dynamic",
            "candidates": ["fast", "code"],
            "defaultProfile": "fast",
        },
    },
    "dynamic": {
        "enabled": True,
        "router": {"provider": "openai", "model": "gpt-4o-mini"},
    },
}


def _write_models(workspace, models: dict) -> None:
    h = workspace / HARNESS_DIR
    h.mkdir(parents=True, exist_ok=True)
    settings_path = h / "settings.json"
    data = {}
    if settings_path.is_file():
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    data["models"] = models
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_build_profile_catalog_from_profiles() -> None:
    catalog = build_profile_catalog(_PROFILES_CFG)
    assert set(catalog) == {"fast", "code"}


@pytest.mark.asyncio
async def test_pick_model_static_when_dynamic_disabled(workspace) -> None:
    models_cfg = {
        **_PROFILES_CFG,
        "dynamic": {"enabled": False},
    }
    _write_models(workspace, models_cfg)
    overrides, note, _ = await pick_model_for_turn(
        workspace,
        mode="ask",
        task="where is auth?",
        turn=1,
        messages=[{"role": "user", "content": "where is auth?"}],
        models_cfg=models_cfg,
    )
    assert overrides["provider"] == "openai"
    assert "ask" in note


@pytest.mark.asyncio
async def test_pick_model_dynamic_uses_router(monkeypatch, workspace) -> None:
    models_cfg = dict(_PROFILES_CFG)
    _write_models(workspace, models_cfg)

    class FakeProvider:
        model = "gpt-4o-mini"

        async def chat(self, messages, tools=None):
            return {"content": '{"profile": "code", "reason": "needs code edits"}'}

    monkeypatch.setattr(
        "meris.provider.dynamic_router.get_provider",
        lambda **kwargs: FakeProvider(),
    )

    overrides, note, reason = await pick_model_for_turn(
        workspace,
        mode="run",
        task="fix failing tests",
        turn=1,
        messages=[{"role": "user", "content": "fix failing tests"}],
        models_cfg=models_cfg,
    )
    assert overrides["provider"] == "anthropic"
    assert note == "dynamic:code"
    assert "edit" in reason


@pytest.mark.asyncio
async def test_pick_model_rule_wins_over_dynamic(workspace) -> None:
    models_cfg = {
        **_PROFILES_CFG,
        "rules": [
            {
                "name": "refactor",
                "match": {"mode": "run", "taskContains": ["重构"]},
                "profile": "code",
            }
        ],
    }
    overrides, note, reason = await pick_model_for_turn(
        workspace,
        mode="run",
        task="大规模重构",
        turn=1,
        messages=[],
        models_cfg=models_cfg,
    )
    assert overrides["provider"] == "anthropic"
    assert note == "refactor:code"
    assert reason == "rule"


def test_needs_reroute_on_first_turn() -> None:
    assert _needs_reroute([], 1) is True


@pytest.mark.asyncio
async def test_pick_model_dynamic_cached_on_mutation_mode(monkeypatch, workspace) -> None:
    models_cfg = {
        **_PROFILES_CFG,
        "dynamic": {
            "enabled": True,
            "reRoute": "onMutation",
            "router": {"provider": "openai", "model": "gpt-4o-mini"},
        },
    }

    calls = {"n": 0}

    class FakeProvider:
        model = "gpt-4o-mini"

        async def chat(self, messages, tools=None):
            calls["n"] += 1
            return {"content": '{"profile": "fast", "reason": "lookup"}'}

    monkeypatch.setattr(
        "meris.provider.dynamic_router.get_provider",
        lambda **kwargs: FakeProvider(),
    )

    last = {"provider": "openai", "model": "gpt-4o-mini"}
    overrides, note, reason = await pick_model_for_turn(
        workspace,
        mode="run",
        task="explain foo",
        turn=2,
        messages=[{"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "read_file"}}]}],
        models_cfg=models_cfg,
        last_overrides=last,
    )
    assert overrides == last
    assert reason == "cached"
    assert calls["n"] == 0
