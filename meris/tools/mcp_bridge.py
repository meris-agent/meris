"""JSONL bridge for meris-rs native agent — keeps MCP sessions alive (P5-4 M3)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from meris.harness.settings import load_settings
from meris.harness.ui_config import get_effective_mcp_servers
from meris.tools.mcp import MCPManager


async def serve_jsonl(workspace: Path) -> None:
    """Read JSONL commands on stdin; write JSONL responses on stdout."""
    settings = load_settings(workspace)
    settings = {**settings, "mcpServers": get_effective_mcp_servers(workspace)}
    servers = settings.get("mcpServers") or {}
    mgr, notes = await MCPManager.connect(servers)
    try:
        print(json.dumps({"event": "ready", "notes": notes}), flush=True)
        while True:
            line = await _readline()
            if line is None:
                break
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                print(json.dumps({"ok": False, "error": str(e)}), flush=True)
                continue
            cmd = req.get("cmd")
            if cmd == "close":
                print(json.dumps({"ok": True}), flush=True)
                break
            if cmd == "schemas":
                read_only = bool(req.get("read_only", False))
                schemas = mgr.tool_schemas_for_llm(read_only=read_only)
                meta = mgr.tool_read_only_flags(read_only=read_only)
                print(
                    json.dumps({"ok": True, "schemas": schemas, "read_only": meta}),
                    flush=True,
                )
            elif cmd == "call":
                tool = str(req.get("tool", ""))
                args = req.get("args") or {}
                if not isinstance(args, dict):
                    args = {}
                result = await mgr.call_meris_tool(tool, args)
                print(json.dumps({"ok": True, "result": result}), flush=True)
            else:
                print(json.dumps({"ok": False, "error": f"unknown cmd: {cmd}"}), flush=True)
    finally:
        await mgr.close()


async def fetch_schemas(
    workspace: Path,
    *,
    read_only: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, bool], list[str]]:
    settings = load_settings(workspace)
    settings = {**settings, "mcpServers": get_effective_mcp_servers(workspace)}
    servers = settings.get("mcpServers") or {}
    mgr, notes = await MCPManager.connect(servers)
    try:
        return (
            mgr.tool_schemas_for_llm(read_only=read_only),
            mgr.tool_read_only_flags(read_only=read_only),
            notes,
        )
    finally:
        await mgr.close()


async def call_tool_once(
    workspace: Path,
    tool: str,
    args: dict[str, Any],
) -> tuple[bool, str]:
    settings = load_settings(workspace)
    settings = {**settings, "mcpServers": get_effective_mcp_servers(workspace)}
    servers = settings.get("mcpServers") or {}
    mgr, notes = await MCPManager.connect(servers)
    try:
        if notes and all(n.startswith("MCP failed") for n in notes if notes):
            pass
        result = await mgr.call_meris_tool(tool, args)
        err = result.startswith("Error:")
        return not err, result
    finally:
        await mgr.close()


async def _readline() -> str | None:
    import asyncio

    line = await asyncio.to_thread(sys.stdin.readline)
    if line == "":
        return None
    return line
