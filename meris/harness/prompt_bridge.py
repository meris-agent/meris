"""System prompt bridge for meris-rs native agent (P5-4 M5)."""

from __future__ import annotations

from pathlib import Path

from meris.harness.guides import build_system_prompt
from meris.harness.memory import load_progress_for_prompt
from meris.harness.spec import load_spec_context


def build_full_system_prompt(workspace: Path, mode: str = "run") -> str:
    """Match Python loop.py initial system message (guides + progress + spec)."""
    system = build_system_prompt(workspace, mode=mode)
    progress = load_progress_for_prompt(workspace)
    spec_ctx = load_spec_context(workspace)
    if progress:
        system += f"\n\n# Progress (read first)\n\n{progress}"
    if spec_ctx:
        system += f"\n\n# Spec\n\n{spec_ctx}"
    return system
