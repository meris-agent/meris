"""Parallel JSONL event stream tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meris.parallel import run_parallel


@pytest.mark.asyncio
async def test_parallel_emits_tagged_events(workspace: Path, monkeypatch) -> None:
    events_path = workspace / ".meris" / "events" / "parallel-test.jsonl"

    async def _fake_loop(ws, task, **kwargs):
        stream = kwargs.get("event_stream")
        assert kwargs.get("native_loop") is False
        if stream:
            stream.emit("token", message=f"ok:{task[:3]}", session="s1", turn=0)
        yield f"line:{task}"

    monkeypatch.setattr("meris.parallel.agent_loop", _fake_loop)

    await run_parallel(
        workspace,
        ["task-a", "task-b"],
        mode="ask",
        max_concurrency=2,
        event_stream_path=events_path,
    )

    lines = [json.loads(ln) for ln in events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    kinds = [e["kind"] for e in lines]
    assert "parallel_start" in kinds
    assert "parallel_done" in kinds
    tokens = [e for e in lines if e.get("kind") == "token"]
    assert len(tokens) == 2
    assert {t["parallel_index"] for t in tokens} == {0, 1}
