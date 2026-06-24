"""Provider abstraction — model-agnostic LLM access."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Provider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return assistant message dict (content + optional tool_calls)."""


class ProviderError(Exception):
    pass
