"""Harness — Tools subsystem (permissions)."""

from __future__ import annotations

import re
from pathlib import Path

from meris.harness.settings import load_settings

# Meris tool name → Claude Code permission category
TOOL_CATEGORY: dict[str, str] = {
    "read_file": "Read",
    "write_file": "Write",
    "edit_file": "Edit",
    "glob": "Glob",
    "grep": "Grep",
    "git_status": "Git",
    "git_diff": "Git",
    "git_commit": "Git",
    "load_skill": "Read",
    "subagent_run": "Read",
    "fetch_url": "Read",
    "lint_file": "Read",
    "bash": "Bash",
}


def _category(tool_name: str) -> str:
    if tool_name.startswith("mcp_"):
        return "MCP"
    return TOOL_CATEGORY.get(tool_name, "Unknown")


def _match_bash_rule(rule: str, command: str) -> bool:
    if not rule.startswith("Bash(") or not rule.endswith(")"):
        return False
    pat = rule[5:-1].replace("*", ".*")
    return bool(re.search(pat, command))


def _allowed_by_rule(rule: str, tool_name: str, args: dict) -> bool:
    rule = rule.strip()
    if rule.startswith("Bash("):
        if tool_name != "bash":
            return False
        return _match_bash_rule(rule, args.get("command", ""))
    cat = _category(tool_name)
    if rule == cat:
        return True
    if rule == "MCP" and tool_name.startswith("mcp_"):
        return True
    return False


def load_permissions(workspace) -> dict:
    return load_settings(workspace)


def check_tool_allowed(
    tool_name: str,
    args: dict,
    settings: dict,
    workspace: Path | None = None,
) -> str | None:
    """Return error message if blocked, else None."""
    if workspace is not None:
        from meris.native import native_check_tool_allowed

        used, err = native_check_tool_allowed(workspace, tool_name, args)
        if used:
            return err

    perms = settings.get("permissions", {})
    deny = perms.get("deny", [])
    allow = perms.get("allow", [])

    if tool_name == "bash":
        cmd = args.get("command", "")
        for rule in deny:
            if _match_bash_rule(rule, cmd):
                return f"Permission denied: {rule}"

    if allow:
        if not any(_allowed_by_rule(rule, tool_name, args) for rule in allow):
            cat = _category(tool_name)
            return f"Permission denied: {tool_name} ({cat}) not in allow list"

    return None
