"""P5-2 — Rust OpenAI-compatible provider."""

from __future__ import annotations

import pytest

from meris.native import native_provider_enabled
from meris.provider.factory import get_provider
from meris.provider.resolve import resolve_provider_config


def test_native_provider_enabled_inherits(monkeypatch) -> None:
    monkeypatch.delenv("MERIS_NATIVE", raising=False)
    monkeypatch.delenv("MERIS_NATIVE_PROVIDER", raising=False)
    monkeypatch.setattr("meris.native.find_native_binary", lambda: __import__("pathlib").Path("/x/meris-rs"))
    assert native_provider_enabled() is True

    monkeypatch.setenv("MERIS_NATIVE_PROVIDER", "0")
    assert native_provider_enabled() is False


def test_get_provider_uses_rust_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("MERIS_NATIVE", "1")
    monkeypatch.setenv("MERIS_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
    monkeypatch.setattr("meris.native.find_native_binary", lambda: __import__("pathlib").Path("/x/meris-rs"))

    from meris.provider.rust_openai import RustOpenAIProvider

    p = get_provider()
    assert isinstance(p, RustOpenAIProvider)


def test_get_provider_python_when_provider_disabled(monkeypatch) -> None:
    monkeypatch.setenv("MERIS_NATIVE_PROVIDER", "0")
    monkeypatch.setenv("MERIS_NATIVE", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
    monkeypatch.setattr("meris.native.find_native_binary", lambda: __import__("pathlib").Path("/x/meris-rs"))

    from meris.provider.openai_compat import OpenAICompatProvider

    p = get_provider(provider="deepseek")
    assert isinstance(p, OpenAICompatProvider)


def test_rust_provider_skipped_for_anthropic(monkeypatch) -> None:
    monkeypatch.setenv("MERIS_NATIVE", "1")
    monkeypatch.setenv("MERIS_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("meris.native.find_native_binary", lambda: __import__("pathlib").Path("/x/meris-rs"))

    try:
        from meris.provider.anthropic import AnthropicProvider

        AnthropicProvider(api_key="sk-ant-test", model="claude-3-5-sonnet")
    except ImportError:
        pytest.skip("anthropic extra not installed")

    p = get_provider()
    assert type(p).__name__ == "AnthropicProvider"


def test_resolve_openai_compat_backend() -> None:
    cfg = resolve_provider_config(provider="deepseek", api_key="k", base_url="https://api.deepseek.com/v1", model="m")
    assert cfg.backend == "openai_compat"
