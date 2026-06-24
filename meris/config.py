"""Environment variable helpers — MERIS_* only."""

from __future__ import annotations

import os


def env_get(name: str, default: str = "") -> str:
    """Read MERIS_{name}."""
    return os.getenv(f"MERIS_{name}", default)


def env_flag(name: str) -> bool:
    val = env_get(name, "")
    return val.lower() in ("1", "true", "yes")


def env_tri(name: str) -> bool | None:
    """Parse MERIS_{name}: True/False if set, None if unset."""
    val = env_get(name, "").strip().lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return None
