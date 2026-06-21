"""Resolve provider, API key, base URL, and model from env + presets."""

from __future__ import annotations

import os
from dataclasses import dataclass

from meris.config import env_get
from meris.provider.presets import ProviderPreset, get_preset, normalize_preset_id


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


_PRESET_URL_HINTS: dict[str, tuple[str, ...]] = {
    "deepseek": ("deepseek",),
    "openai": ("openai.com",),
    "gemini": ("generativelanguage.googleapis.com", "google"),
    "glm": ("bigmodel.cn", "zhipu"),
    "moonshot": ("moonshot.cn",),
    "qwen": ("dashscope", "aliyuncs"),
    "volcengine": ("volces.com", "volcengine"),
    "groq": ("groq.com",),
    "mistral": ("mistral.ai",),
    "openrouter": ("openrouter.ai",),
    "ollama": ("11434", "ollama"),
    "local": ("localhost", "127.0.0.1"),
}


def _base_url_matches_preset(url: str, preset_id: str) -> bool:
    u = url.lower()
    hints = _PRESET_URL_HINTS.get(preset_id, ())
    return any(h in u for h in hints)


_PRESET_BASE_URL_ENV: dict[str, tuple[str, ...]] = {
    "deepseek": ("DEEPSEEK_BASE_URL",),
    "openai": ("OPENAI_BASE_URL",),
    "gemini": ("GEMINI_BASE_URL", "GOOGLE_BASE_URL"),
    "glm": ("GLM_BASE_URL", "ZHIPU_BASE_URL"),
    "moonshot": ("MOONSHOT_BASE_URL", "KIMI_BASE_URL"),
    "qwen": ("DASHSCOPE_BASE_URL", "QWEN_BASE_URL", "BAILIAN_BASE_URL"),
    "volcengine": ("VOLCENGINE_BASE_URL", "ARK_BASE_URL", "DOUBAO_BASE_URL"),
    "local": ("LOCAL_BASE_URL", "VLLM_BASE_URL"),
    "groq": ("GROQ_BASE_URL",),
    "mistral": ("MISTRAL_BASE_URL",),
    "openrouter": ("OPENROUTER_BASE_URL",),
    "ollama": ("OLLAMA_BASE_URL",),
}


def _preset_base_url_from_env(preset_id: str) -> str:
    for name in _PRESET_BASE_URL_ENV.get(preset_id, ()):
        val = os.getenv(name, "").strip()
        if val:
            return val
    return ""


def _global_base_url_from_env() -> str:
    return (env_get("BASE_URL") or os.getenv("LLM_BASE_URL", "")).strip()


def _resolve_base_url(
    *,
    preset_id: str,
    default_base: str,
    explicit_base: str | None,
) -> str:
    """Config overrides preset default: route/settings → vendor env → MERIS_BASE_URL → built-in."""
    if explicit_base:
        return explicit_base
    preset_env = _preset_base_url_from_env(preset_id)
    if preset_env:
        return preset_env
    global_base = _global_base_url_from_env()
    if global_base and _base_url_matches_preset(global_base, preset_id):
        return global_base
    return default_base


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


_PRESET_MODEL_ENV: dict[str, tuple[str, ...]] = {
    "deepseek": ("DEEPSEEK_MODEL",),
    "openai": ("OPENAI_MODEL",),
    "anthropic": ("ANTHROPIC_MODEL",),
    "gemini": ("GEMINI_MODEL",),
    "glm": ("GLM_MODEL",),
    "moonshot": ("MOONSHOT_MODEL", "KIMI_MODEL"),
    "qwen": ("DASHSCOPE_MODEL", "QWEN_MODEL"),
    "volcengine": ("VOLCENGINE_MODEL", "ARK_MODEL", "DOUBAO_MODEL"),
    "groq": ("GROQ_MODEL",),
    "mistral": ("MISTRAL_MODEL",),
    "openrouter": ("OPENROUTER_MODEL",),
    "ollama": ("OLLAMA_MODEL",),
}


def _preset_model_from_env(preset_id: str) -> str:
    for name in _PRESET_MODEL_ENV.get(preset_id, ()):
        val = os.getenv(name, "").strip()
        if val:
            return val
    return ""


def _resolve_model(
    *,
    preset_id: str,
    default_model: str,
    explicit_model: str | None,
    has_explicit_model: bool,
) -> str:
    if has_explicit_model:
        return explicit_model or ""
    preset_env = _preset_model_from_env(preset_id)
    if preset_env:
        return preset_env
    return env_get("MODEL") or os.getenv("LLM_MODEL", "") or default_model


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

    has_explicit_model = bool((model or "").strip())

    if backend == "anthropic":
        resolved_base = ""
    else:
        resolved_base = _resolve_base_url(
            preset_id=preset_id,
            default_base=default_base,
            explicit_base=base_url,
        )
        if preset_id == "ollama" and not resolved_key:
            resolved_key = os.getenv("OLLAMA_API_KEY") or "ollama"

    resolved_model = _resolve_model(
        preset_id=preset_id,
        default_model=default_model,
        explicit_model=model,
        has_explicit_model=has_explicit_model,
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
