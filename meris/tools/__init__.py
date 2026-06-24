from meris.tools.builtin import build_tools
from meris.tools.mcp import MCPManager, MCP_AVAILABLE
from meris.tools.registry import Tool, ToolRegistry

__all__ = ["Tool", "ToolRegistry", "build_tools", "build_all_tools", "MCPManager", "MCP_AVAILABLE"]


async def build_all_tools(
    workspace,
    *,
    read_only: bool = False,
    settings: dict | None = None,
) -> tuple[ToolRegistry, MCPManager | None, list[str]]:
    """Build builtin + MCP tools. Returns (registry, mcp_manager, notes)."""
    reg = build_tools(workspace, read_only=read_only)
    notes: list[str] = []
    manager: MCPManager | None = None
    servers = (settings or {}).get("mcpServers") or {}
    if servers:
        manager, notes = await MCPManager.connect(servers)
        if manager.servers:
            n = manager.register_tools(reg, read_only=read_only)
            notes.append(f"Registered {n} MCP tools")
    return reg, manager, notes
