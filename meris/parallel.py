"""Parallel session orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path

from meris.harness.sessions import new_session_id
from meris.loop import agent_loop
from meris.tools.worktree import WorktreeInfo, create_worktree, remove_worktree


@dataclass
class ParallelResult:
    index: int
    task: str
    session_id: str
    status: str
    lines: list[str]


async def run_parallel(
    workspace: Path,
    tasks: list[str],
    *,
    mode: str = "ask",
    max_concurrency: int = 3,
    isolate: bool = False,
    max_turns: int = 30,
    on_line: Callable[[int, str], None] | None = None,
) -> list[ParallelResult]:
    """Run multiple agent sessions concurrently."""
    sem = asyncio.Semaphore(max(1, max_concurrency))

    async def _one(index: int, task: str) -> ParallelResult:
        session_id = new_session_id()
        lines: list[str] = []
        status = "completed"
        wt: WorktreeInfo | None = None
        ws = workspace.resolve()
        prefix = f"[parallel-{index}]"

        async with sem:
            try:
                if isolate and mode == "run":
                    wt = await create_worktree(ws, label=session_id)
                    ws = wt.path

                async for line in agent_loop(
                    ws,
                    task,
                    mode=mode,
                    max_turns=max_turns,
                    session_id=session_id,
                    run_sensors_at_end=mode == "run" and not isolate,
                ):
                    tagged = f"{prefix} {line}"
                    lines.append(tagged)
                    if on_line:
                        on_line(index, tagged)
            except Exception as e:
                status = "error"
                err = f"{prefix} Error: {e}"
                lines.append(err)
                if on_line:
                    on_line(index, err)
            finally:
                if wt:
                    try:
                        await remove_worktree(workspace.resolve(), wt)
                    except Exception as exc:
                        lines.append(f"{prefix} worktree cleanup: {exc}")

        return ParallelResult(
            index=index, task=task, session_id=session_id, status=status, lines=lines
        )

    return list(await asyncio.gather(*[_one(i, t) for i, t in enumerate(tasks)]))


async def stream_parallel(
    workspace: Path,
    tasks: list[str],
    **kwargs,
) -> AsyncIterator[tuple[int, str]]:
    queue: asyncio.Queue[tuple[int, str] | None] = asyncio.Queue()

    def on_line(i: int, line: str) -> None:
        queue.put_nowait((i, line))

    async def _run() -> None:
        await run_parallel(workspace, tasks, on_line=on_line, **kwargs)
        await queue.put(None)

    runner = asyncio.create_task(_run())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        await runner
