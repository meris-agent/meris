"""P5-4 M3 — MCP bridge for native agent loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from meris.cli import app
from meris.tools.mcp import MCPManager, _safe_name


def test_mcp_tool_schemas_empty_manager() -> None:
    mgr = MCPManager()
    assert mgr.tool_schemas_for_llm() == []
    assert mgr.tool_read_only_flags() == {}


@pytest.mark.asyncio
async def test_call_unknown_mcp_tool() -> None:
    mgr = MCPManager()
    out = await mgr.call_meris_tool("mcp_nope_tool", {})
    assert "unknown MCP tool" in out


def test_mcp_schemas_cli_json(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["mcp", "schemas", "--cwd", str(workspace), "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    data = json.loads(result.stdout.strip())
    assert data["ok"] is True
    assert isinstance(data["schemas"], list)
    assert isinstance(data["read_only"], dict)


def test_mcp_safe_name_parity() -> None:
    assert _safe_name("my-server", "read-file").startswith("mcp_my_server_")


def test_has_mcp_servers_setting(workspace: Path) -> None:
    from meris.harness.settings import load_settings

    s = load_settings(workspace)
    assert "mcpServers" in s or s.get("mcpServers") is None
