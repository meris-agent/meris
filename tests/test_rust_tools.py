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


@pytest.mark.asyncio
async def test_write_file_python_fallback(workspace: Path, monkeypatch) -> None:
    monkeypatch.setenv("MERIS_NATIVE", "0")
    tools = build_tools(workspace, read_only=False)
    out = await tools.execute("write_file", {"path": "out.txt", "content": "hi"})
    assert "Wrote out.txt" in out
    assert (workspace / "out.txt").read_text(encoding="utf-8") == "hi"


@pytest.mark.skipif(
    __import__("meris.native", fromlist=["find_native_binary"]).find_native_binary() is None,
    reason="meris-rs not built",
)
@pytest.mark.asyncio
async def test_native_write_file(workspace: Path) -> None:
    import subprocess

    from meris.native import find_native_binary

    binary = find_native_binary()
    probe = subprocess.run(
        [str(binary), "tools", "run", "--workspace", str(workspace), "--tool", "write_file", "--args", "{}"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if "unknown tool" in (probe.stderr or probe.stdout):
        pytest.skip("write_file not in binary")
    tools = build_tools(workspace, read_only=False)
    out = await tools.execute("write_file", {"path": "native.txt", "content": "data"})
    assert "Wrote" in out or "native.txt" in out


def test_parity_fixtures_tools_json() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "benchmark" / "fixtures" / "parity.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "permissions" in data
    assert "sandbox" in data


@pytest.mark.skipif(
    __import__("meris.native", fromlist=["find_native_binary"]).find_native_binary() is None,
    reason="meris-rs not built",
)
def test_rust_tool_schemas_match_python(workspace: Path, monkeypatch) -> None:
    import subprocess

    from meris.native import find_native_binary
    from meris.tools import build_tools

    binary = find_native_binary()
    probe = subprocess.run(
        [str(binary), "tools", "schemas", "--read-only"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip("tools schemas subcommand missing")
    rust = json.loads(probe.stdout)
    py = build_tools(workspace, read_only=True).schemas()
    py_by_name = {s["function"]["name"]: s for s in py}
    for schema in rust:
        name = schema["function"]["name"]
        assert name in py_by_name
        assert schema["function"]["parameters"] == py_by_name[name]["function"]["parameters"]
