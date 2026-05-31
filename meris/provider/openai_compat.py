"""OpenAI-compatible provider (DeepSeek, GLM, Ollama, etc.)."""

from __future__ import annotations

import os
from typing import Any

from openai import AsyncOpenAI

from meris.config import env_get
from meris.provider.base import Provider, ProviderError


class OpenAICompatProvider(Provider):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.model = (
            model
            or env_get("MODEL")
            or os.getenv("LLM_MODEL")
            or os.getenv("DEEPSEEK_MODEL")
            or "deepseek-chat"
        )
        key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or "not-needed"
        )
        url = (
            base_url
            or env_get("BASE_URL")
            or os.getenv("LLM_BASE_URL")
            or os.getenv("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com/v1"
        )
        self.client = AsyncOpenAI(api_key=key, base_url=url)

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
