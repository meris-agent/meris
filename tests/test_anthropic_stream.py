"""Tests for AnthropicProvider.chat_stream (Phase H7)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("anthropic")

from meris.provider.anthropic import AnthropicProvider


class _FakeStream:
    def __init__(self, text_parts: list[str], final_blocks: list) -> None:
        self._text_parts = text_parts
        self._final_blocks = final_blocks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def __aiter__(self):
        self._iter = iter(self._text_parts)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None

    @property
    def text_stream(self):
        return self

    async def get_final_message(self):
        return SimpleNamespace(content=self._final_blocks)


@pytest.mark.asyncio
async def test_anthropic_chat_stream_yields_tokens() -> None:
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.model = "claude-test"
    provider.client = MagicMock()

    final_blocks = [SimpleNamespace(type="text", text="Hello")]
    fake_stream = _FakeStream(["Hel", "lo"], final_blocks)
    provider.client.messages.stream = MagicMock(return_value=fake_stream)

    items = []
    async for item in provider.chat_stream([{"role": "user", "content": "hi"}]):
        items.append(item)

    assert items[0] == {"type": "token", "delta": "Hel"}
    assert items[1] == {"type": "token", "delta": "lo"}
    assert items[-1]["type"] == "done"
    assert items[-1]["message"]["content"] == "Hello"
