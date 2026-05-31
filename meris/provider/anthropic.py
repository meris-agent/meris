"""Anthropic native provider (Claude Messages API)."""

from __future__ import annotations

import json
import os
from typing import Any

from meris.config import env_get
from meris.provider.base import Provider, ProviderError

try:
    from anthropic import AsyncAnthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class AnthropicProvider(Provider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("pip install anthropic — or meris-agent[anthropic]")
        self.model = model or env_get("MODEL") or os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514"
        key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY") or ""
        self.client = AsyncAnthropic(api_key=key)

    def _to_anthropic_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if not tools:
            return None
        out: list[dict[str, Any]] = []
        for t in tools:
            fn = t.get("function") or t
            out.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        return out

    def _split_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        convo: list[dict[str, Any]] = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                if m.get("content"):
                    system_parts.append(str(m["content"]))
            elif role == "tool":
                convo.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.get("tool_call_id", "tool"),
                                "content": str(m.get("content") or ""),
                            }
                        ],
                    }
                )
            elif role == "assistant" and m.get("tool_calls"):
                blocks: list[dict[str, Any]] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": str(m["content"])})
                for tc in m["tool_calls"]:
                    fn = tc.get("function") or {}
                    args_raw = fn.get("arguments", "{}")
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    except json.JSONDecodeError:
                        args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", fn.get("name", "tool")),
                            "name": fn.get("name", ""),
                            "input": args,
                        }
                    )
                convo.append({"role": "assistant", "content": blocks})
            else:
                convo.append({"role": role, "content": str(m.get("content") or "")})
        return "\n\n".join(system_parts), convo

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        system, convo = self._split_messages(messages)
        if not convo:
            convo = [{"role": "user", "content": "(empty)"}]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 8192,
            "messages": convo,
        }
        if system:
            kwargs["system"] = system
        anthropic_tools = self._to_anthropic_tools(tools)
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        try:
            resp = await self.client.messages.create(**kwargs)
        except Exception as e:
            raise ProviderError(str(e)) from e

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input, ensure_ascii=False),
                        },
                    }
                )

        msg: dict[str, Any] = {"role": "assistant", "content": "".join(text_parts)}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return msg
