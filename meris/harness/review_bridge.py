"""Review task bridge for meris-rs native agent (Phase F2-M1)."""

from __future__ import annotations

from pathlib import Path

from meris.harness.review import build_review_task


def build_review_task_for_native(workspace: Path, *, staged: bool = False) -> str:
    return build_review_task(workspace, staged=staged)
