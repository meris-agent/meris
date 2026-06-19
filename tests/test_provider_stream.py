"""Tests for live token streaming in agent loop (Phase H6)."""

from __future__ import annotations

import pytest

from meris.harness.protocol import EventStream
from meris.loop import _provider_chat_with_events


class _StreamProvider:
    async def chat_stream(self, messages, tools=None):
        yield {"type": "reasoning", "delta": "think", "chunk": 0}
        yield {"type": "token", "delta": "Hel"}
        yield {"type": "token", "delta": "lo"}
        yield {"type": "done", "message": {"role": "assistant", "content": "Hello"}}


class _BatchProvider:
    async def chat(self, messages, tools=None):
        return {"role": "assistant", "content": "Hi there"}


@pytest.mark.asyncio
async def test_provider_chat_stream_emits_tokens() -> None:
    stream = EventStream(collector=[])
    msg = await _provider_chat_with_events(
        _StreamProvider(),
        [],
        None,
        event_stream=stream,
        session="abc",
        turn=2,
    )
    assert msg["content"] == "Hello"
    kinds = [e["kind"] for e in stream.collector or []]
    assert kinds.count("token") == 2
    assert kinds.count("reasoning") == 1


@pytest.mark.asyncio
async def test_provider_chat_stream_emits_reasoning() -> None:
    stream = EventStream(collector=[])
    await _provider_chat_with_events(
        _StreamProvider(),
        [],
        None,
        event_stream=stream,
        session="abc",
        turn=2,
    )
    kinds = [e["kind"] for e in stream.collector or []]
    assert "reasoning" in kinds


@pytest.mark.asyncio
async def test_provider_chat_batch_chunks_when_no_stream() -> None:
    stream = EventStream(collector=[])
    msg = await _provider_chat_with_events(
        _BatchProvider(),
        [],
        None,
        event_stream=stream,
        session="abc",
        turn=1,
    )
    assert msg["content"] == "Hi there"
    assert any(e["kind"] == "token" for e in stream.collector or [])
