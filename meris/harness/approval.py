"""File-based approval channel for IDE / Agent Window consumers (Phase H3)."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from meris.harness.protocol import EventStream


def approval_paths(channel: Path) -> tuple[Path, Path]:
    """Return (request, response) paths under channel directory."""
    d = channel if channel.is_dir() else channel.parent
    d.mkdir(parents=True, exist_ok=True)
    return d / "approval-request.json", d / "approval-response.json"


async def wait_for_approval(
    *,
    channel: Path,
    tool: str,
    args: dict[str, Any],
    event_stream: EventStream | None = None,
    session: str = "",
    turn: int = 0,
    timeout: float = 600,
    poll_interval: float = 0.15,
) -> bool:
    """Block until consumer writes approval-response.json or timeout."""
    request_id = uuid.uuid4().hex[:12]
    req_path, res_path = approval_paths(channel)
    res_path.unlink(missing_ok=True)
    payload = {
        "request_id": request_id,
        "tool": tool,
        "args": args,
        "ts": time.time(),
        "session": session,
        "turn": turn,
    }
    req_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    if event_stream:
        event_stream.emit(
            "approval_request",
            tool=tool,
            args=args,
            request_id=request_id,
            session=session,
            turn=turn,
        )

    deadline = time.time() + timeout
    while time.time() < deadline:
        if res_path.is_file():
            try:
                data = json.loads(res_path.read_text(encoding="utf-8"))
                if data.get("request_id") == request_id:
                    res_path.unlink(missing_ok=True)
                    req_path.unlink(missing_ok=True)
                    return bool(data.get("approved"))
            except (json.JSONDecodeError, OSError):
                pass
        await asyncio.sleep(poll_interval)

    req_path.unlink(missing_ok=True)
    return False
