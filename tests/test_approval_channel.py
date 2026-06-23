"""Tests for file-based approval channel."""

from __future__ import annotations

import asyncio
import json

import pytest

from meris.harness.approval import approval_paths, wait_for_approval
from meris.harness.protocol import EventStream


@pytest.mark.asyncio
async def test_wait_for_approval_approved(tmp_path) -> None:
    channel = tmp_path / "approval"
    events: list[dict] = []
    stream = EventStream(collector=events)

    async def respond() -> None:
        await asyncio.sleep(0.25)
        _, res_path = approval_paths(channel)
        req_path, _ = approval_paths(channel)
        data = json.loads(req_path.read_text(encoding="utf-8"))
        res_path.write_text(
            json.dumps({"request_id": data["request_id"], "approved": True}),
            encoding="utf-8",
        )

    task = asyncio.create_task(respond())
    ok = await wait_for_approval(
        channel=channel,
        tool="write_file",
        args={"path": "foo.txt"},
        event_stream=stream,
        timeout=5,
    )
    await task
    assert ok is True
    assert any(e.get("kind") == "approval_request" for e in events)


@pytest.mark.asyncio
async def test_wait_for_approval_denied(tmp_path) -> None:
    channel = tmp_path / "approval"

    async def respond() -> None:
        await asyncio.sleep(0.2)
        _, res_path = approval_paths(channel)
        req_path, _ = approval_paths(channel)
        data = json.loads(req_path.read_text(encoding="utf-8"))
        res_path.write_text(
            json.dumps({"request_id": data["request_id"], "approved": False}),
            encoding="utf-8",
        )

    task = asyncio.create_task(respond())
    ok = await wait_for_approval(
        channel=channel,
        tool="bash",
        args={"command": "rm -rf /"},
        timeout=5,
    )
    await task
    assert ok is False


@pytest.mark.asyncio
async def test_wait_for_approval_timeout(tmp_path) -> None:
    channel = tmp_path / "approval"
    ok = await wait_for_approval(
        channel=channel,
        tool="write_file",
        args={},
        timeout=0.4,
        poll_interval=0.1,
    )
    assert ok is False
