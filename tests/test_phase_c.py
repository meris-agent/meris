"""Phase C — token context, anthropic factory, extras tools."""

from __future__ import annotations

import pytest

from meris.harness.context import (
    compress_messages,
    estimate_messages_tokens,
    estimate_tokens,
    shrink_tool_results,
    truncate_content,
)
from meris.provider.factory import get_provider


def test_estimate_tokens() -> None:
    assert estimate_tokens("abcd") >= 1
    assert estimate_tokens("") == 0


def test_truncate_content() -> None:
    long = "x" * 10000
    out = truncate_content(long, max_tokens=100)
    assert "truncated" in out
    assert len(out) < len(long)


def test_compress_by_tokens() -> None:
    msgs = [{"role": "system", "content": "sys"}]
    msgs.append({"role": "user", "content": "original task"})
    for i in range(30):
        msgs.append({"role": "assistant", "content": "a" * 500})
        msgs.append({"role": "user", "content": "u" * 500})
    out = compress_messages(msgs, max_messages=100, max_tokens=3000)
    assert estimate_messages_tokens(out) <= 3500
    assert any(m.get("role") == "user" and "original" in m.get("content", "") for m in out)


def test_shrink_tool_results() -> None:
    msgs = [{"role": "tool", "content": "x" * 20000, "tool_call_id": "1"}]
    out = shrink_tool_results(msgs, max_tool_tokens=100)
    assert "truncated" in out[0]["content"]


def test_anthropic_split_messages() -> None:
    from meris.provider.anthropic import AnthropicProvider

    provider = AnthropicProvider.__new__(AnthropicProvider)
    system, convo = provider._split_messages(
        [
            {"role": "system", "content": "guide"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
    )
    assert "guide" in system
    assert len(convo) == 2


def test_get_provider_openai_default(monkeypatch) -> None:
    monkeypatch.delenv("MERIS_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    p = get_provider()
    assert p.__class__.__name__ == "OpenAICompatProvider"


@pytest.mark.asyncio
async def test_fetch_url_invalid_async(workspace) -> None:
    from meris.tools import build_tools

    tools = build_tools(workspace, read_only=True)
    out = await tools.execute("fetch_url", {"url": "ftp://bad"})
    assert "Error" in out


@pytest.mark.asyncio
async def test_lint_file_missing(workspace) -> None:
    from meris.tools import build_tools

    tools = build_tools(workspace, read_only=True)
    out = await tools.execute("lint_file", {"path": "missing.py"})
    assert "Error" in out
