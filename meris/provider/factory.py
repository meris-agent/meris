"""Provider factory — select LLM backend from environment."""

from __future__ import annotations

import os

from meris.config import env_get
from meris.provider.base import Provider
from meris.provider.openai_compat import OpenAICompatProvider


def get_provider(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> Provider:
    """Return provider based on MERIS_PROVIDER (openai | anthropic)."""
    kind = (env_get("PROVIDER") or os.getenv("LLM_PROVIDER") or "openai").lower()

    if kind in ("anthropic", "claude"):
        try:
            from meris.provider.anthropic import AnthropicProvider
        except ImportError as e:
            raise ImportError(
                "Anthropic provider requires: pip install meris-agent[anthropic]"
            ) from e
        return AnthropicProvider(api_key=api_key, model=model)

    return OpenAICompatProvider(api_key=api_key, base_url=base_url, model=model)
