"""Harness directory — `.meris/`."""

from __future__ import annotations

from pathlib import Path

HARNESS_DIR = ".meris"


def harness_root(workspace: Path) -> Path:
    """Return harness dot-directory for a workspace."""
    return workspace.resolve() / HARNESS_DIR
