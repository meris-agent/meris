"""OpenAI-compatible provider (DeepSeek, OpenAI, Gemini, GLM, Ollama, etc.)."""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from meris.provider.base import Provider, ProviderError
from meris.provider.resolve import resolve_provider_config


class OpenAICompatProvider(Provider):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        cfg = resolve_provider_config(api_key=api_key, base_url=base_url, model=model)
        self.model = cfg.model
        key = cfg.api_key or "not-needed"
        self.client = AsyncOpenAI(api_key=key, base_url=cfg.base_url)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        try:
            kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            resp = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            raise ProviderError(str(e)) from e

        choice = resp.choices[0].message
        msg: dict[str, Any] = {"role": "assistant", "content": choice.content or ""}
        if choice.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.tool_calls
            ]
        return msg
