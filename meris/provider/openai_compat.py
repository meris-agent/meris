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

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ):
        """Yield token deltas, then a final done message (OpenAI streaming API)."""
        try:
            kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "stream": True}
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            stream = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            raise ProviderError(str(e)) from e

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_by_index: dict[int, dict[str, Any]] = {}
        reasoning_chunk = 0

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning_delta = getattr(delta, "reasoning_content", None) or getattr(
                delta, "reasoning", None
            )
            if reasoning_delta:
                reasoning_parts.append(reasoning_delta)
                yield {"type": "reasoning", "delta": reasoning_delta, "chunk": reasoning_chunk}
                reasoning_chunk += 1
            if delta.content:
                content_parts.append(delta.content)
                yield {"type": "token", "delta": delta.content}
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_by_index:
                        tool_calls_by_index[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    acc = tool_calls_by_index[idx]
                    if tc.id:
                        acc["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            acc["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            acc["function"]["arguments"] += tc.function.arguments

        content = "".join(content_parts)
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if reasoning_parts:
            msg["reasoning_content"] = "".join(reasoning_parts)
        if tool_calls_by_index:
            ordered = [tool_calls_by_index[i] for i in sorted(tool_calls_by_index)]
            msg["tool_calls"] = ordered
        yield {"type": "done", "message": msg}
