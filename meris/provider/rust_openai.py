"""OpenAI-compatible provider via meris-rs (P5-2)."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from meris.native import find_native_binary, native_provider_chat
from meris.provider.base import Provider, ProviderError
from meris.provider.resolve import resolve_provider_config


class RustOpenAIProvider(Provider):
    """Delegate chat completions to `meris-rs provider chat` (OpenAI-compatible APIs only)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        cfg = resolve_provider_config(api_key=api_key, base_url=base_url, model=model)
        if cfg.backend != "openai_compat":
            raise ProviderError(f"Rust provider supports openai_compat only, not {cfg.backend}")
        self.model = cfg.model
        self.base_url = cfg.base_url

    @staticmethod
    def available() -> bool:
        return find_native_binary() is not None

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result = await asyncio.to_thread(
            native_provider_chat,
            messages,
            tools,
            self.base_url,
            self.model,
        )
        if result is None:
            raise ProviderError("meris-rs provider chat failed or unavailable")
        return result
