"""Harness event protocol — SQ/EQ shape for UI and CI."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, TextIO


class EventStream:
    """Write JSONL events; optional in-memory collector for exec --json."""

    def __init__(
        self,
        sink: TextIO | None = None,
        *,
        collector: list[dict[str, Any]] | None = None,
    ) -> None:
        self._sink = sink
        self.collector = collector

    @classmethod
    def open(cls, path: Path | str | None) -> EventStream | None:
        if path is None:
            return None
        p = Path(path) if path != "-" else None
        if path == "-":
            return cls(sys.stdout)
        assert p is not None
        p.parent.mkdir(parents=True, exist_ok=True)
        return cls(p.open("a", encoding="utf-8"))

    @classmethod
    def memory(cls) -> EventStream:
        return cls(collector=[])

    def emit(self, kind: str, *, message: str = "", **fields: Any) -> None:
        data: dict[str, Any] = {"type": "event", "ts": time.time(), "kind": kind}
        if message:
            data["message"] = message
        data.update(fields)
        if self.collector is not None:
            self.collector.append(data)
        if self._sink is not None:
            self._sink.write(json.dumps(data, ensure_ascii=False) + "\n")
            self._sink.flush()

    def close(self) -> None:
        if self._sink is not None and self._sink not in (sys.stdout, sys.stderr):
            self._sink.close()


class TaggedEventStream:
    """Proxy that adds fixed tags to every emitted event (parallel lanes, etc.)."""

    def __init__(self, base: EventStream, **tags: Any) -> None:
        self._base = base
        self._tags = tags

    def emit(self, kind: str, *, message: str = "", **fields: Any) -> None:
        self._base.emit(kind, message=message, **{**self._tags, **fields})

    def close(self) -> None:
        return


def emit_submission(stream: EventStream | None, *, action: str, task: str = "", session: str = "") -> None:
    if not stream:
        return
    stream.emit("submission", message=action, action=action, task=task[:500], session=session)
