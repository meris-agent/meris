"""Harness — Hooks (PreToolUse / PostToolUse)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class HookResult:
    block: bool = False
    message: str = ""


HookFn = Callable[[str, dict[str, Any]], Awaitable[HookResult]]
PostHookFn = Callable[[str, dict[str, Any], str], Awaitable[HookResult]]


class HookRunner:
    def __init__(self) -> None:
        self.pre: list[HookFn] = []
        self.post: list[PostHookFn] = []

    def on_pre(self, fn: HookFn) -> None:
        self.pre.append(fn)

    def on_post(self, fn: PostHookFn) -> None:
        self.post.append(fn)

    async def run_pre(self, tool: str, args: dict[str, Any]) -> HookResult:
        for fn in self.pre:
            r = await fn(tool, args)
            if r.block:
                return r
        return HookResult()

    async def run_post(self, tool: str, args: dict[str, Any], result: str) -> HookResult:
        for fn in self.post:
            r = await fn(tool, args, result)
            if r.block:
                return r
        return HookResult()
