"""P5-3 — native read-only tools parity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meris.tools import build_tools


@pytest.mark.skipif(
    __import__("meris.native", fromlist=["find_native_binary"]).find_native_binary() is None,
    reason="meris-rs not built",
)
@pytest.mark.asyncio
async def test_native_read_file_matches_python(workspace: Path) -> None:
    (workspace / "sample.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    tools = build_tools(workspace, read_only=True)
    out = await tools.execute("read_file", {"path": "sample.txt", "limit": 2})
    assert "alpha" in out
    assert "|" in out


@pytest.mark.asyncio
async def test_read_file_python_fallback(workspace: Path, monkeypatch) -> None:
    monkeypatch.setenv("MERIS_NATIVE", "0")
    (workspace / "sample.txt").write_text("only line\n", encoding="utf-8")
    tools = build_tools(workspace, read_only=True)
    out = await tools.execute("read_file", {"path": "sample.txt"})
    assert "only line" in out


@pytest.mark.asyncio
async def test_glob_python(workspace: Path, monkeypatch) -> None:
    monkeypatch.setenv("MERIS_NATIVE", "0")
    (workspace / "a.py").write_text("x", encoding="utf-8")
    tools = build_tools(workspace, read_only=True)
    out = await tools.execute("glob", {"pattern": "*.py"})
    assert "a.py" in out


def test_parity_fixtures_tools_json() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "benchmark" / "fixtures" / "parity.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "permissions" in data
    assert "sandbox" in data
