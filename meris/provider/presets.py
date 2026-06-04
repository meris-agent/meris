"""Built-in LLM provider presets (OpenAI-compatible + Anthropic native)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    """One selectable backend; env vars can override base_url / model."""

    id: str
    label: str
    backend: str  # openai_compat | anthropic
    base_url: str = ""
    default_model: str = ""
    api_key_env: tuple[str, ...] = ()
    docs_url: str = ""


PRESETS: dict[str, ProviderPreset] = {
    "deepseek": ProviderPreset(
        id="deepseek",
        label="DeepSeek",
        backend="openai_compat",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        api_key_env=("DEEPSEEK_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"),
        docs_url="https://platform.deepseek.com/",
    ),
    "openai": ProviderPreset(
        id="openai",
        label="OpenAI",
        backend="openai_compat",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        api_key_env=("OPENAI_API_KEY", "LLM_API_KEY"),
        docs_url="https://platform.openai.com/",
    ),
    "anthropic": ProviderPreset(
        id="anthropic",
        label="Anthropic Claude",
        backend="anthropic",
        default_model="claude-sonnet-4-20250514",
        api_key_env=("ANTHROPIC_API_KEY", "LLM_API_KEY"),
        docs_url="https://console.anthropic.com/",
    ),
    "gemini": ProviderPreset(
        id="gemini",
        label="Google Gemini (OpenAI-compatible)",
        backend="openai_compat",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        default_model="gemini-2.0-flash",
        api_key_env=("GEMINI_API_KEY", "GOOGLE_API_KEY", "LLM_API_KEY"),
        docs_url="https://ai.google.dev/gemini-api/docs",
    ),
    "glm": ProviderPreset(
        id="glm",
        label="Zhipu GLM",
        backend="openai_compat",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        default_model="glm-4-flash",
        api_key_env=("ZHIPU_API_KEY", "GLM_API_KEY", "LLM_API_KEY"),
        docs_url="https://open.bigmodel.cn/",
    ),
    "moonshot": ProviderPreset(
        id="moonshot",
        label="Moonshot / Kimi",
        backend="openai_compat",
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-8k",
        api_key_env=("MOONSHOT_API_KEY", "KIMI_API_KEY", "LLM_API_KEY"),
        docs_url="https://platform.moonshot.cn/",
    ),
    "qwen": ProviderPreset(
        id="qwen",
        label="Alibaba Qwen / 百炼 (DashScope OpenAI-compatible)",
        backend="openai_compat",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        api_key_env=("DASHSCOPE_API_KEY", "QWEN_API_KEY", "BAILIAN_API_KEY", "LLM_API_KEY"),
        docs_url="https://help.aliyun.com/zh/model-studio/developer-reference/compatibility-of-openai-with-dashscope/",
    ),
    "volcengine": ProviderPreset(
        id="volcengine",
        label="Volcengine 火山方舟 / 豆包 (Ark OpenAI-compatible)",
        backend="openai_compat",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_model="doubao-pro-32k",
        api_key_env=("ARK_API_KEY", "VOLCENGINE_API_KEY", "DOUBAO_API_KEY", "LLM_API_KEY"),
        docs_url="https://www.volcengine.com/docs/82379/1099455",
    ),
    "local": ProviderPreset(
        id="local",
        label="Self-hosted (vLLM / Xinference / LocalAI / LiteLLM proxy)",
        backend="openai_compat",
        base_url="http://127.0.0.1:8000/v1",
        default_model="default",
        api_key_env=("OPENAI_API_KEY", "LLM_API_KEY"),
        docs_url="https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html",
    ),
    "groq": ProviderPreset(
        id="groq",
        label="Groq",
        backend="openai_compat",
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        api_key_env=("GROQ_API_KEY", "LLM_API_KEY"),
        docs_url="https://console.groq.com/",
    ),
    "mistral": ProviderPreset(
        id="mistral",
        label="Mistral",
        backend="openai_compat",
        base_url="https://api.mistral.ai/v1",
        default_model="mistral-small-latest",
        api_key_env=("MISTRAL_API_KEY", "LLM_API_KEY"),
        docs_url="https://console.mistral.ai/",
    ),
    "openrouter": ProviderPreset(
        id="openrouter",
        label="OpenRouter (multi-model gateway)",
        backend="openai_compat",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4o-mini",
        api_key_env=("OPENROUTER_API_KEY", "LLM_API_KEY"),
        docs_url="https://openrouter.ai/docs",
    ),
    "ollama": ProviderPreset(
        id="ollama",
        label="Ollama (local)",
        backend="openai_compat",
        base_url="http://127.0.0.1:11434/v1",
        default_model="llama3.2",
        api_key_env=("OLLAMA_API_KEY",),  # optional; client uses placeholder if empty
        docs_url="https://ollama.com/",
    ),
}

# Aliases → canonical preset id
PRESET_ALIASES: dict[str, str] = {
    "claude": "anthropic",
    "google": "gemini",
    "zhipu": "glm",
    "chatglm": "glm",
    "kimi": "moonshot",
    "dashscope": "qwen",
    "tongyi": "qwen",
    "bailian": "qwen",
    "aliyun": "qwen",
    "volc": "volcengine",
    "ark": "volcengine",
    "doubao": "volcengine",
    "huoshan": "volcengine",
    "vllm": "local",
    "xinference": "local",
    "localai": "local",
    "litellm": "local",
    "self-hosted": "local",
    "selfhosted": "local",
    "custom": "local",
    "azure": "openai",  # use MERIS_BASE_URL for Azure OpenAI endpoint
    "azure_openai": "openai",
}


def normalize_preset_id(raw: str) -> str:
    key = (raw or "").strip().lower()
    if not key:
        return ""
    if key in PRESETS:
        return key
    return PRESET_ALIASES.get(key, key)


def list_preset_ids() -> list[str]:
    return sorted(PRESETS.keys())


def get_preset(preset_id: str) -> ProviderPreset | None:
    canon = normalize_preset_id(preset_id)
    return PRESETS.get(canon)
