"""Built-in coding tools."""

from __future__ import annotations

import asyncio
import glob as globlib
import os
import re
from pathlib import Path

from meris.tools.registry import Tool, ToolRegistry


def _resolve(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    if not str(p).startswith(str(root.resolve())):
        raise PermissionError(f"path escapes workspace: {rel}")
    return p


def build_tools(workspace: Path, read_only: bool = False) -> ToolRegistry:
    reg = ToolRegistry()

    async def read_file(args: dict) -> str:
        p = _resolve(workspace, args["path"])
        if not p.is_file():
            return f"Error: not a file: {args['path']}"
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        offset = max(0, int(args.get("offset", 1)) - 1)
        limit = int(args.get("limit", 200))
        chunk = lines[offset : offset + limit]
        numbered = "\n".join(f"{i + offset + 1:4}| {ln}" for i, ln in enumerate(chunk))
        return numbered or "(empty file)"

    reg.register(
        Tool(
            name="read_file",
            description="Read a file with line numbers. Use offset/limit for large files.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path from repo root"},
                    "offset": {"type": "integer", "description": "Start line (1-based)"},
                    "limit": {"type": "integer", "description": "Max lines to read"},
                },
                "required": ["path"],
            },
            handler=read_file,
            read_only=True,
        )
    )

    if not read_only:

        async def write_file(args: dict) -> str:
            p = _resolve(workspace, args["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"], encoding="utf-8")
            return f"Wrote {args['path']} ({len(args['content'])} bytes)"

        async def edit_file(args: dict) -> str:
            p = _resolve(workspace, args["path"])
            if not p.is_file():
                return f"Error: not a file: {args['path']}"
            text = p.read_text(encoding="utf-8")
            old, new = args["old_string"], args["new_string"]
            if old not in text:
                return "Error: old_string not found in file"
            p.write_text(text.replace(old, new, 1), encoding="utf-8")
            return f"Edited {args['path']}"

        reg.register(
            Tool(
                name="write_file",
                description="Create or overwrite a file.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
                handler=write_file,
            )
        )
        reg.register(
            Tool(
                name="edit_file",
                description="Replace exactly one occurrence of old_string with new_string.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
                handler=edit_file,
            )
        )

        async def bash(args: dict) -> str:
            from meris.config import env_flag
            from meris.harness.settings import load_settings
            from meris.harness.sandbox import get_bash_timeout
            from meris.native import native_run_bash

            cmd = args["command"]
            settings = load_settings(workspace)
            timeout = get_bash_timeout(settings)
            if env_flag("NATIVE"):
                native_out = native_run_bash(workspace, cmd, timeout=timeout)
                if native_out is not None:
                    return native_out

            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            text = out.decode("utf-8", errors="replace")
            return f"exit={proc.returncode}\n{text[-8000:]}"

        reg.register(
            Tool(
                name="bash",
                description="Run shell command in repo root. Prefer rg/grep/test over cat.",
                parameters={
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
                handler=bash,
            )
        )

    async def glob_search(args: dict) -> str:
        pattern = args["pattern"]
        matches = sorted(globlib.glob(str(workspace / pattern), recursive=True))[:50]
        rel = [os.path.relpath(m, workspace) for m in matches]
        return "\n".join(rel) if rel else "(no matches)"

    async def grep(args: dict) -> str:
        pattern = args["pattern"]
        path = args.get("path", ".")
        root = _resolve(workspace, path)
        hits: list[str] = []
        rx = re.compile(pattern)
        for fp in root.rglob("*") if root.is_dir() else [root]:
            if not fp.is_file() or fp.stat().st_size > 500_000:
                continue
            try:
                for i, line in enumerate(fp.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if rx.search(line):
                        rel = fp.relative_to(workspace)
                        hits.append(f"{rel}:{i}:{line[:200]}")
                        if len(hits) >= 40:
                            return "\n".join(hits)
            except OSError:
                continue
        return "\n".join(hits) if hits else "(no matches)"

    reg.register(
        Tool(
            name="glob",
            description="Find files by glob pattern relative to repo root.",
            parameters={
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            },
            handler=glob_search,
            read_only=True,
        )
    )
    reg.register(
        Tool(
            name="grep",
            description="Regex search in files. Optional path (file or dir).",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["pattern"],
            },
            handler=grep,
            read_only=True,
        )
    )

    async def fetch_url(args: dict) -> str:
        import httpx

        url = args.get("url", "").strip()
        if not url.startswith(("http://", "https://")):
            return "Error: url must start with http:// or https://"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                resp = await client.get(url)
                text = resp.text[:12000]
                return f"status={resp.status_code}\n{text}"
        except Exception as e:
            return f"Error fetching url: {e}"

    async def lint_file(args: dict) -> str:
        path = args.get("path", "")
        p = _resolve(workspace, path)
        if not p.is_file():
            return f"Error: not a file: {path}"
        proc = await asyncio.create_subprocess_exec(
            "python",
            "-m",
            "ruff",
            "check",
            str(p),
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        text = out.decode("utf-8", errors="replace")
        if proc.returncode == 0:
            return text or "(no lint issues)"
        return f"exit={proc.returncode}\n{text}"

    reg.register(
        Tool(
            name="fetch_url",
            description="HTTP GET a URL and return text content (read-only, max 12k chars).",
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            handler=fetch_url,
            read_only=True,
        )
    )
    reg.register(
        Tool(
            name="lint_file",
            description="Run ruff check on a single file (LSP-lite diagnostics).",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=lint_file,
            read_only=True,
        )
    )

    async def git_status(args: dict) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "status",
            "--short",
            "--branch",
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        text = out.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            return f"git status failed (exit={proc.returncode})\n{text}"
        return text or "(clean working tree)"

    async def git_diff(args: dict) -> str:
        cmd = ["git", "diff"]
        if args.get("staged"):
            cmd.append("--staged")
        path = args.get("path")
        if path:
            cmd.append("--")
            cmd.append(path)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        text = out.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            return f"git diff failed (exit={proc.returncode})\n{text}"
        return text[:12000] or "(no diff)"

    reg.register(
        Tool(
            name="git_status",
            description="Show git status (branch + short status). Read-only.",
            parameters={"type": "object", "properties": {}},
            handler=git_status,
            read_only=True,
        )
    )
    reg.register(
        Tool(
            name="git_diff",
            description="Show git diff. Optional staged=true or path filter.",
            parameters={
                "type": "object",
                "properties": {
                    "staged": {"type": "boolean", "description": "Diff staged changes only"},
                    "path": {"type": "string", "description": "Limit diff to path"},
                },
            },
            handler=git_diff,
            read_only=True,
        )
    )

    async def load_skill(args: dict) -> str:
        from meris.harness.skills import load_skill_content, list_skills

        name = args.get("name", "")
        content = load_skill_content(workspace, name)
        if content is None:
            available = ", ".join(list_skills(workspace)) or "(none)"
            return f"Error: skill '{name}' not found. Available: {available}"
        return content

    reg.register(
        Tool(
            name="load_skill",
            description="Load on-demand skill doc from .meris/skills/{name}.md",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Skill name without .md"}},
                "required": ["name"],
            },
            handler=load_skill,
            read_only=True,
        )
    )

    if not read_only:

        async def git_commit(args: dict) -> str:
            message = args.get("message", "")
            if not message.strip():
                return "Error: commit message required"
            proc = await asyncio.create_subprocess_exec(
                "git",
                "commit",
                "-m",
                message,
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            text = out.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                return f"git commit failed (exit={proc.returncode})\n{text}"
            return text.strip() or "(committed)"

        reg.register(
            Tool(
                name="git_commit",
                description="Create git commit for staged changes. Stage files with bash git add first.",
                parameters={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Commit message"},
                    },
                    "required": ["message"],
                },
                handler=git_commit,
            )
        )

        async def subagent_run(args: dict) -> str:
            from meris.loop import agent_loop

            task = args.get("task", "")
            if not task:
                return "Error: task required"
            sub_mode = args.get("mode", "ask")
            sub_turns = min(int(args.get("max_turns", 8)), 15)
            lines: list[str] = []
            async for line in agent_loop(
                workspace,
                task,
                mode=sub_mode,
                max_turns=sub_turns,
                run_sensors_at_end=False,
            ):
                lines.append(line)
            return "\n".join(lines)[-8000:]

        reg.register(
            Tool(
                name="subagent_run",
                description="Delegate a sub-task to an isolated read-only subagent (context isolation).",
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Sub-task prompt"},
                        "mode": {
                            "type": "string",
                            "enum": ["ask", "plan"],
                            "description": "Subagent mode (default ask)",
                        },
                        "max_turns": {"type": "integer", "description": "Max turns (default 8, max 15)"},
                    },
                    "required": ["task"],
                },
                handler=subagent_run,
                read_only=True,
            )
        )

    return reg
