"""Append-only conversation state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    """Mutable view over append-only message history."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    turn: int = 0
    max_turns: int = 30

    def append(self, message: dict[str, Any]) -> None:
        self.messages.append(message)

    def extend(self, messages: list[dict[str, Any]]) -> None:
        self.messages.extend(messages)

    @property
    def done(self) -> bool:
        return self.turn >= self.max_turns

    def next_turn(self) -> None:
        self.turn += 1

    @classmethod
    def from_session(cls, messages: list[dict], turn: int, max_turns: int) -> AgentState:
        state = cls(max_turns=max_turns)
        state.messages = list(messages)
        state.turn = turn
        return state
