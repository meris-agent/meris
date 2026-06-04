"""Provider factory — select LLM backend from environment."""

from __future__ import annotations

from meris.provider.base import Provider
from meris.provider.openai_compat import OpenAICompatProvider
from meris.provider.resolve import resolve_provider_config


def get_provider(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> Provider:
    """Return provider from MERIS_PROVIDER preset or env (see ``meris models list``)."""
    cfg = resolve_provider_config(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )

    if cfg.backend == "anthropic":
        try:
            from meris.provider.anthropic import AnthropicProvider
        except ImportError as e:
            raise ImportError(
                "Anthropic provider requires: pip install meris-agent[anthropic]"
            ) from e
        return AnthropicProvider(api_key=cfg.api_key or None, model=cfg.model)

    return OpenAICompatProvider(
        api_key=cfg.api_key or None,
        base_url=cfg.base_url or None,
        model=cfg.model,
    )
