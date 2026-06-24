"""MCP client — tools, resources, prompts via stdio or SSE."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from meris.tools.registry import Tool, ToolRegistry

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

try:
    from mcp.client.sse import sse_client

    MCP_SSE_AVAILABLE = True
except ImportError:
    MCP_SSE_AVAILABLE = False


def _safe_name(server: str, tool: str) -> str:
    raw = f"mcp_{server}_{tool}"
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)[:64]


def _content_blocks_text(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) if parts else ""


def _tool_result_text(result: Any) -> str:
    text = _content_blocks_text(result)
    if text:
        return text
    if getattr(result, "isError", False):
        return "MCP tool returned an error"
    return "(empty MCP result)"


@dataclass
class MCPServerConnection:
    name: str
    transport: str = "stdio"
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""
    session: Any = None
    tools: list[Any] = field(default_factory=list)
    resources: list[Any] = field(default_factory=list)
    prompts: list[Any] = field(default_factory=list)
    _transport_ctx: Any = None
    _session_ctx: Any = None

    async def connect(self) -> None:
        if not MCP_AVAILABLE:
            raise RuntimeError("mcp package not installed — pip install meris-agent[mcp]")

        if self.transport == "sse":
            if not MCP_SSE_AVAILABLE:
                raise RuntimeError("MCP SSE transport unavailable")
            if not self.url:
                raise RuntimeError("SSE transport requires url")
            self._transport_ctx = sse_client(self.url)
        else:
            params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env={**os.environ, **self.env} if self.env else None,
            )
            self._transport_ctx = stdio_client(params)

        read, write = await self._transport_ctx.__aenter__()
        self._session_ctx = ClientSession(read, write)
        self.session = await self._session_ctx.__aenter__()
        await self.session.initialize()
        listed = await self.session.list_tools()
        self.tools = list(listed.tools)
        try:
            lr = await self.session.list_resources()
            self.resources = list(lr.resources)
        except Exception:
            self.resources = []
        try:
            lp = await self.session.list_prompts()
            self.prompts = list(lp.prompts)
        except Exception:
            self.prompts = []

    async def disconnect(self) -> None:
        if self._session_ctx is not None:
            await self._session_ctx.__aexit__(None, None, None)
            self._session_ctx = None
        if self._transport_ctx is not None:
            await self._transport_ctx.__aexit__(None, None, None)
            self._transport_ctx = None
        self.session = None

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if not self.session:
            return f"Error: MCP server {self.name} not connected"
        result = await self.session.call_tool(tool_name, arguments=arguments)
        return _tool_result_text(result)

    async def read_resource(self, uri: str) -> str:
        if not self.session:
            return f"Error: MCP server {self.name} not connected"
        result = await self.session.read_resource(uri)
        text = _content_blocks_text(result)
        if hasattr(result, "contents"):
            for c in result.contents:
                if getattr(c, "text", None):
                    text += c.text
                elif getattr(c, "blob", None):
                    text += f"[binary blob {len(c.blob)} bytes]"
        return text[:16000] or "(empty resource)"

    async def get_prompt(self, prompt_name: str, arguments: dict[str, Any] | None = None) -> str:
        if not self.session:
            return f"Error: MCP server {self.name} not connected"
        result = await self.session.get_prompt(prompt_name, arguments=arguments or {})
        messages = getattr(result, "messages", []) or []
        parts: list[str] = []
        for msg in messages:
            content = getattr(msg, "content", None)
            if isinstance(content, str):
                parts.append(content)
            elif hasattr(content, "text"):
                parts.append(content.text)
        return "\n".join(parts)[:16000] or "(empty prompt)"


class MCPManager:
    def __init__(self) -> None:
        self.servers: dict[str, MCPServerConnection] = {}

    @classmethod
    async def connect(cls, servers_cfg: dict[str, Any]) -> tuple[MCPManager, list[str]]:
        mgr = cls()
        notes: list[str] = []
        if not MCP_AVAILABLE:
            notes.append("MCP skipped: install with pip install meris-agent[mcp]")
            return mgr, notes
        for name, cfg in servers_cfg.items():
            if cfg.get("disabled"):
                continue
            transport = cfg.get("transport", "stdio")
            conn = MCPServerConnection(
                name=name,
                transport=transport,
                command=cfg.get("command", ""),
                args=list(cfg.get("args") or []),
                env=dict(cfg.get("env") or {}),
                url=cfg.get("url", ""),
            )
            try:
                await conn.connect()
                mgr.servers[name] = conn
                notes.append(
                    f"MCP connected: {name} ({transport}, "
                    f"{len(conn.tools)} tools, {len(conn.resources)} resources, "
                    f"{len(conn.prompts)} prompts)"
                )
            except Exception as e:
                notes.append(f"MCP failed {name}: {e}")
        return mgr, notes

    async def close(self) -> None:
        for conn in self.servers.values():
            await conn.disconnect()
        self.servers.clear()

    def _server(self, server_name: str) -> MCPServerConnection | None:
        return self.servers.get(server_name)

    def register_tools(self, registry: ToolRegistry, *, read_only: bool = False) -> int:
        count = 0
        for server_name, conn in self.servers.items():
            for mcp_tool in conn.tools:
                meris_name = _safe_name(server_name, mcp_tool.name)
                schema = dict(mcp_tool.inputSchema or {"type": "object", "properties": {}})
                is_read_only = read_only or not schema.get("properties")

                async def handler(
                    args: dict[str, Any],
                    _conn: MCPServerConnection = conn,
                    _tool: str = mcp_tool.name,
                ) -> str:
                    return await _conn.call(_tool, args)

                registry.register(
                    Tool(
                        name=meris_name,
                        description=f"[MCP:{server_name}] {mcp_tool.description or mcp_tool.name}",
                        parameters=schema,
                        handler=handler,
                        read_only=is_read_only,
                    )
                )
                count += 1

            if conn.resources:

                async def resource_handler(
                    args: dict[str, Any],
                    _conn: MCPServerConnection = conn,
                    _srv: str = server_name,
                ) -> str:
                    uri = args.get("uri", "")
                    if not uri:
                        uris = [getattr(r, "uri", str(r)) for r in _conn.resources[:20]]
                        return f"Error: uri required. Available: {uris}"
                    return await _conn.read_resource(uri)

                registry.register(
                    Tool(
                        name=f"mcp_{server_name}_read_resource",
                        description=f"[MCP:{server_name}] Read MCP resource by URI",
                        parameters={
                            "type": "object",
                            "properties": {"uri": {"type": "string"}},
                            "required": ["uri"],
                        },
                        handler=resource_handler,
                        read_only=True,
                    )
                )
                count += 1

            if conn.prompts:

                async def prompt_handler(
                    args: dict[str, Any],
                    _conn: MCPServerConnection = conn,
                ) -> str:
                    name = args.get("name", "")
                    arguments = args.get("arguments") or {}
                    if not name:
                        names = [getattr(p, "name", str(p)) for p in _conn.prompts[:20]]
                        return f"Error: name required. Available prompts: {names}"
                    return await _conn.get_prompt(name, arguments)

                registry.register(
                    Tool(
                        name=f"mcp_{server_name}_get_prompt",
                        description=f"[MCP:{server_name}] Get MCP prompt template",
                        parameters={
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "arguments": {"type": "object"},
                            },
                            "required": ["name"],
                        },
                        handler=prompt_handler,
                        read_only=True,
                    )
                )
                count += 1

        return count

    def tool_schemas_for_llm(self, *, read_only: bool = False) -> list[dict[str, Any]]:
        """OpenAI function schemas for connected MCP tools (no handlers)."""
        schemas: list[dict[str, Any]] = []
        for server_name, conn in self.servers.items():
            for mcp_tool in conn.tools:
                meris_name = _safe_name(server_name, mcp_tool.name)
                schema = dict(mcp_tool.inputSchema or {"type": "object", "properties": {}})
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": meris_name,
                            "description": f"[MCP:{server_name}] {mcp_tool.description or mcp_tool.name}",
                            "parameters": schema,
                        },
                    }
                )
            if conn.resources:
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": f"mcp_{server_name}_read_resource",
                            "description": f"[MCP:{server_name}] Read MCP resource by URI",
                            "parameters": {
                                "type": "object",
                                "properties": {"uri": {"type": "string"}},
                                "required": ["uri"],
                            },
                        },
                    }
                )
            if conn.prompts:
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": f"mcp_{server_name}_get_prompt",
                            "description": f"[MCP:{server_name}] Get MCP prompt template",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "arguments": {"type": "object"},
                                },
                                "required": ["name"],
                            },
                        },
                    }
                )
        return schemas

    def tool_read_only_flags(self, *, read_only: bool = False) -> dict[str, bool]:
        flags: dict[str, bool] = {}
        for server_name, conn in self.servers.items():
            for mcp_tool in conn.tools:
                meris_name = _safe_name(server_name, mcp_tool.name)
                schema = dict(mcp_tool.inputSchema or {"type": "object", "properties": {}})
                flags[meris_name] = read_only or not schema.get("properties")
            if conn.resources:
                flags[f"mcp_{server_name}_read_resource"] = True
            if conn.prompts:
                flags[f"mcp_{server_name}_get_prompt"] = True
        return flags

    async def call_meris_tool(self, meris_name: str, args: dict[str, Any]) -> str:
        for server_name, conn in self.servers.items():
            for mcp_tool in conn.tools:
                if _safe_name(server_name, mcp_tool.name) == meris_name:
                    return await conn.call(mcp_tool.name, args)
            if meris_name == f"mcp_{server_name}_read_resource":
                uri = args.get("uri", "")
                if not uri:
                    uris = [getattr(r, "uri", str(r)) for r in conn.resources[:20]]
                    return f"Error: uri required. Available: {uris}"
                return await conn.read_resource(uri)
            if meris_name == f"mcp_{server_name}_get_prompt":
                name = args.get("name", "")
                arguments = args.get("arguments") or {}
                if not name:
                    names = [getattr(p, "name", str(p)) for p in conn.prompts[:20]]
                    return f"Error: name required. Available prompts: {names}"
                return await conn.get_prompt(name, arguments)
        return f"Error: unknown MCP tool {meris_name}"

    def list_tools_summary(self) -> list[str]:
        lines: list[str] = []
        for server_name, conn in self.servers.items():
            for t in conn.tools:
                lines.append(
                    f"  tool  {server_name}/{t.name} → {_safe_name(server_name, t.name)}"
                )
            for r in conn.resources:
                uri = getattr(r, "uri", str(r))
                lines.append(f"  resource  {server_name}/{uri}")
            for p in conn.prompts:
                pname = getattr(p, "name", str(p))
                lines.append(f"  prompt  {server_name}/{pname}")
        return lines
