"""Session resume tests — dogfood P4 persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from meris.harness.sessions import SessionRecord, load_session, save_session
from meris.loop import agent_loop


class _MockProvider:
    model = "mock"

    def __init__(self, responses: list[dict] | None = None) -> None:
        self._responses = list(responses or [{"content": "done", "tool_calls": None}])
        self.calls = 0

    async def chat(self, messages, tools=None):
        self.calls += 1
        if self.calls <= len(self._responses):
            return self._responses[self.calls - 1]
        return {"content": "done", "tool_calls": None}


@pytest.mark.asyncio
async def test_session_resume_continues_messages(workspace: Path) -> None:
    """Resume should not rebuild system prompt; provider sees prior messages."""
    rec = SessionRecord(
        id="resume02",
        task="explain hello.py",
        mode="ask",
        status="running",
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "explain hello.py"},
            {"role": "assistant", "content": "partial answer"},
        ],
        turn=1,
        max_turns=10,
        workspace=str(workspace),
    )
    save_session(workspace, rec)

    provider = _MockProvider([{"content": "final answer", "tool_calls": None}])
    lines: list[str] = []

    async for line in agent_loop(
        workspace,
        "ignored-on-resume",
        mode="ask",
        provider=provider,
        session_id="resume02",
        resume=True,
        max_turns=10,
        run_sensors_at_end=False,
    ):
        lines.append(line)

    assert any("resumed session=resume02" in ln for ln in lines)
    assert provider.calls == 1

    final = load_session(workspace, "resume02")
    assert final is not None
    assert final.status == "completed"
    assert any(m.get("content") == "final answer" for m in final.messages)
    assert any(m.get("content") == "partial answer" for m in final.messages)


@pytest.mark.asyncio
async def test_session_id_persisted_on_fresh_run(workspace: Path) -> None:
    provider = _MockProvider()
    sid = "fixed-id-01"

    async for _ in agent_loop(
        workspace,
        "ping",
        mode="ask",
        provider=provider,
        session_id=sid,
        max_turns=5,
        run_sensors_at_end=False,
    ):
        pass

    loaded = load_session(workspace, sid)
    assert loaded is not None
    assert loaded.task == "ping"
    assert loaded.status == "completed"
    assert len(loaded.messages) >= 2
