"""Resolve provider, API key, base URL, and model from env + presets."""

from __future__ import annotations

import os
from dataclasses import dataclass

from meris.config import env_get
from meris.provider.presets import PRESETS, ProviderPreset, get_preset, normalize_preset_id


@dataclass
class ResolvedProviderConfig:
    preset_id: str
    label: str
    backend: str  # openai_compat | anthropic
    api_key: str
    base_url: str
    model: str
    key_env_hint: str  # primary env var name for doctor messages


def _first_env(names: tuple[str, ...]) -> tuple[str, str]:
    for name in names:
        val = os.getenv(name, "").strip()
        if val:
            return name, val
    return (names[0] if names else "LLM_API_KEY", "")


def _infer_preset_from_keys() -> str:
    """Guess preset when MERIS_PROVIDER is unset."""
    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        return "anthropic"
    if os.getenv("DEEPSEEK_API_KEY", "").strip() and not os.getenv("OPENAI_API_KEY", "").strip():
        return "deepseek"
    if os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip():
        return "gemini"
    if os.getenv("ZHIPU_API_KEY", "").strip() or os.getenv("GLM_API_KEY", "").strip():
        return "glm"
    if os.getenv("MOONSHOT_API_KEY", "").strip() or os.getenv("KIMI_API_KEY", "").strip():
        return "moonshot"
    if (
        os.getenv("DASHSCOPE_API_KEY", "").strip()
        or os.getenv("QWEN_API_KEY", "").strip()
        or os.getenv("BAILIAN_API_KEY", "").strip()
    ):
        return "qwen"
    if (
        os.getenv("ARK_API_KEY", "").strip()
        or os.getenv("VOLCENGINE_API_KEY", "").strip()
        or os.getenv("DOUBAO_API_KEY", "").strip()
    ):
        return "volcengine"
    if os.getenv("GROQ_API_KEY", "").strip():
        return "groq"
    if os.getenv("MISTRAL_API_KEY", "").strip():
        return "mistral"
    if os.getenv("OPENROUTER_API_KEY", "").strip():
        return "openrouter"
    if os.getenv("OPENAI_API_KEY", "").strip():
        return "openai"
    if os.getenv("LLM_API_KEY", "").strip():
        # Legacy DeepSeek-oriented setups often only set LLM_API_KEY + deepseek URL
        base = (
            env_get("BASE_URL")
            or os.getenv("LLM_BASE_URL", "")
            or os.getenv("DEEPSEEK_BASE_URL", "")
        ).lower()
        if "deepseek" in base:
            return "deepseek"
        if "openrouter" in base:
            return "openrouter"
        if "moonshot" in base:
            return "moonshot"
        if "bigmodel" in base or "zhipu" in base:
            return "glm"
        if "dashscope" in base or "aliyuncs" in base:
            return "qwen"
        if "volces.com" in base or "volcengine" in base:
            return "volcengine"
        if ":8000" in base or ":8080" in base or "vllm" in base:
            return "local"
        if "groq" in base:
            return "groq"
        if "mistral" in base:
            return "mistral"
        if "generativelanguage" in base or "google" in base:
            return "gemini"
        if "11434" in base or "ollama" in base:
            return "ollama"
        return "openai"
    return "openai"


def resolve_provider_config(
    *,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> ResolvedProviderConfig:
    """Merge explicit args with MERIS_* / legacy env and built-in presets."""
    raw_provider = (
        provider
        or env_get("PROVIDER")
        or os.getenv("LLM_PROVIDER", "")
    ).strip()
    preset_id = normalize_preset_id(raw_provider) if raw_provider else _infer_preset_from_keys()

    preset: ProviderPreset | None = get_preset(preset_id)
    if preset is None:
        # Unknown id: treat as custom OpenAI-compatible
        preset_id = raw_provider or "custom"
        backend = "anthropic" if preset_id in ("anthropic", "claude") else "openai_compat"
        label = f"custom ({preset_id})"
        default_base = ""
        default_model = ""
        key_envs: tuple[str, ...] = (
            ("ANTHROPIC_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
            if backend == "anthropic"
            else ("OPENAI_API_KEY", "LLM_API_KEY", "DEEPSEEK_API_KEY")
        )
    else:
        backend = preset.backend
        label = preset.label
        default_base = preset.base_url
        default_model = preset.default_model
        key_envs = preset.api_key_env

    key_env_hint, resolved_key = _first_env(key_envs)
    if api_key is not None:
        resolved_key = api_key

    if backend == "anthropic":
        resolved_base = ""
    else:
        resolved_base = (
            base_url
            or env_get("BASE_URL")
            or os.getenv("LLM_BASE_URL", "")
            or os.getenv("DEEPSEEK_BASE_URL", "")
            or default_base
        )
        if preset_id == "ollama" and not resolved_key:
            resolved_key = os.getenv("OLLAMA_API_KEY") or "ollama"

    resolved_model = (
        model
        or env_get("MODEL")
        or os.getenv("LLM_MODEL", "")
        or os.getenv("ANTHROPIC_MODEL", "")
        or os.getenv("DEEPSEEK_MODEL", "")
        or default_model
    )

    if not resolved_key and backend == "openai_compat" and preset_id == "ollama":
        resolved_key = "ollama"

    return ResolvedProviderConfig(
        preset_id=preset_id if preset else preset_id,
        label=label,
        backend=backend,
        api_key=resolved_key,
        base_url=resolved_base,
        model=resolved_model,
        key_env_hint=key_env_hint,
    )
