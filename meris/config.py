"""Environment variable helpers — MERIS_* with legacy FORGE_* fallback."""

from __future__ import annotations

import os


def env_get(name: str, default: str = "") -> str:
    """Read MERIS_{name} or legacy FORGE_{name}."""
    meris = os.getenv(f"MERIS_{name}")
    if meris:
        return meris
    legacy = os.getenv(f"FORGE_{name}")
    if legacy:
        return legacy
    return default


def env_flag(name: str) -> bool:
    val = env_get(name, "")
    return val.lower() in ("1", "true", "yes")
