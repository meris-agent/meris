"""Profile catalog and mode binding."""

from __future__ import annotations

from meris.provider.profiles import (
    build_candidate_catalog,
    build_profiles_catalog,
    mode_strategy,
    resolve_profile,
)


def test_profiles_catalog_explicit() -> None:
    cfg = {
        "profiles": {
            "fast": {"provider": "deepseek", "model": "deepseek-chat"},
            "code": {"provider": "volcengine", "model": "ep-x"},
        }
    }
    catalog = build_profiles_catalog(cfg)
    assert set(catalog) == {"fast", "code"}
    assert resolve_profile(cfg, "code")["provider"] == "volcengine"


def test_mode_strategy_dynamic() -> None:
    cfg = {
        "profiles": {"fast": {"provider": "deepseek", "model": "x"}},
        "byMode": {"run": {"strategy": "dynamic", "candidates": ["fast"]}},
    }
    assert mode_strategy(cfg, "run") == "dynamic"
    assert mode_strategy(cfg, "ask") == "static"


def test_candidate_catalog_subset() -> None:
    cfg = {
        "profiles": {
            "fast": {"provider": "deepseek", "model": "a"},
            "code": {"provider": "volcengine", "model": "b"},
            "heavy": {"provider": "anthropic", "model": "c"},
        },
        "byMode": {
            "run": {"strategy": "dynamic", "candidates": ["fast", "code"], "defaultProfile": "fast"}
        },
    }
    catalog = build_candidate_catalog(cfg, "run")
    assert set(catalog) == {"fast", "code"}
