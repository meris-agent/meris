"""Harness directory — `.meris/` (legacy `.forge/` fallback)."""

from __future__ import annotations

from pathlib import Path

HARNESS_DIR = ".meris"
LEGACY_HARNESS_DIR = ".forge"


def harness_root(workspace: Path) -> Path:
    """Return active harness dot-directory for a workspace."""
    ws = workspace.resolve()
    meris = ws / HARNESS_DIR
    legacy = ws / LEGACY_HARNESS_DIR
    if meris.is_dir() or not legacy.is_dir():
        return meris
    return legacy
