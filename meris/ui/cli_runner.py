"""Safe one-shot CLI execution from Agent Window (allowlist only)."""

from __future__ import annotations

# command id → meris argv (after `meris`)
RUNNABLE_CLI: dict[str, list[str]] = {
    "doctor": ["doctor", "--no-probe"],
    "dogfood": ["dogfood"],
    "harness-check": ["harness", "check"],
    "ratchet-status": ["ratchet", "status"],
    "ratchet-scan": ["ratchet", "scan"],
    "native-status": ["native", "status"],
    "mcp-list": ["mcp", "list"],
    "release-check": ["release", "check"],
    "session-list": ["session", "list"],
    "models-route": ["models", "route", "preview routing smoke"],
    "benchmark": ["benchmark", "run", "--local-only"],
}


def resolve_runnable_cli(command_id: str) -> list[str] | None:
    """Return meris subcommand argv if *command_id* is allowed to run from UI."""
    key = (command_id or "").strip()
    if not key:
        return None
    argv = RUNNABLE_CLI.get(key)
    return list(argv) if argv else None
