"""Ratchet workspace paths under `.meris/ratchet/`."""

from __future__ import annotations

from pathlib import Path

from meris.harness.paths import harness_root

RATCHET_DIR = "ratchet"


def ratchet_root(workspace: Path) -> Path:
    d = harness_root(workspace) / RATCHET_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def events_file(workspace: Path) -> Path:
    return ratchet_root(workspace) / "events.jsonl"


def proposals_dir(workspace: Path) -> Path:
    d = ratchet_root(workspace) / "proposals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def applied_dir(workspace: Path) -> Path:
    d = ratchet_root(workspace) / "applied"
    d.mkdir(parents=True, exist_ok=True)
    return d


def insights_dir(workspace: Path) -> Path:
    d = ratchet_root(workspace) / "insights"
    d.mkdir(parents=True, exist_ok=True)
    return d
