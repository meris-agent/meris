"""Provider preset resolution."""

from __future__ import annotations


import pytest

from meris.provider.presets import get_preset, normalize_preset_id
from meris.provider.resolve import resolve_provider_config


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("openai", "openai"),
        ("kimi", "moonshot"),
        ("claude", "anthropic"),
        ("google", "gemini"),
        ("bailian", "qwen"),
        ("doubao", "volcengine"),
        ("vllm", "local"),
    ],
)
def test_normalize_preset_id(raw: str, expected: str) -> None:
    assert normalize_preset_id(raw) == expected


def _clear_meris_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        "MERIS_PROVIDER",
        "MERIS_BASE_URL",
        "MERIS_MODEL",
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "ARK_BASE_URL",
        "VOLCENGINE_BASE_URL",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "ARK_API_KEY",
        "VOLCENGINE_API_KEY",
        "DOUBAO_API_KEY",
        "LLM_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)


def test_resolve_openai_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meris_llm_env(monkeypatch)
    monkeypatch.setenv("MERIS_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = resolve_provider_config()
    assert cfg.preset_id == "openai"
    assert cfg.backend == "openai_compat"
    assert cfg.base_url == "https://api.openai.com/v1"
    assert cfg.model == "gpt-4o-mini"
    assert cfg.api_key == "sk-test"


def test_resolve_deepseek_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meris_llm_env(monkeypatch)
    monkeypatch.setenv("MERIS_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    cfg = resolve_provider_config()
    assert cfg.preset_id == "deepseek"
    assert "deepseek.com" in cfg.base_url
    assert cfg.model == "deepseek-chat"


def test_resolve_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meris_llm_env(monkeypatch)
    monkeypatch.setenv("MERIS_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
    cfg = resolve_provider_config()
    assert cfg.backend == "anthropic"
    assert cfg.base_url == ""
    assert "claude" in cfg.model


def test_infer_deepseek_from_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meris_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.setenv("MERIS_BASE_URL", "https://api.deepseek.com/v1")
    cfg = resolve_provider_config()
    assert cfg.preset_id == "deepseek"


def test_meris_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meris_llm_env(monkeypatch)
    monkeypatch.setenv("MERIS_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("MERIS_MODEL", "custom-model")
    cfg = resolve_provider_config()
    assert cfg.model == "custom-model"


def test_get_preset_unknown() -> None:
    assert get_preset("not-a-vendor") is None


def test_models_list_cli() -> None:
    from typer.testing import CliRunner

    from meris.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["models", "list"])
    assert result.exit_code == 0
    assert "deepseek" in result.output
    assert "openai" in result.output


def test_routed_volcengine_ignores_global_deepseek_base(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meris_llm_env(monkeypatch)
    monkeypatch.setenv("MERIS_BASE_URL", "https://api.deepseek.com/v1")
    cfg = resolve_provider_config(provider="volcengine", model="ep-test")
    assert "volces.com" in cfg.base_url
    assert "deepseek" not in cfg.base_url
    assert cfg.model == "ep-test"


def test_volcengine_uses_vendor_base_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meris_llm_env(monkeypatch)
    monkeypatch.setenv("ARK_BASE_URL", "https://ark.cn-shanghai.volces.com/api/v3")
    cfg = resolve_provider_config(provider="volcengine", model="ep-test")
    assert cfg.base_url == "https://ark.cn-shanghai.volces.com/api/v3"


def test_deepseek_uses_vendor_base_url_over_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meris_llm_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://custom.deepseek.example/v1")
    cfg = resolve_provider_config(provider="deepseek")
    assert cfg.base_url == "https://custom.deepseek.example/v1"


def test_routed_model_uses_vendor_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meris_llm_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    cfg = resolve_provider_config(provider="deepseek")
    assert cfg.model == "deepseek-reasoner"
