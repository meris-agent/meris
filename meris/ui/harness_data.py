"""Harness catalog helpers for Agent Window UI (workspace / files / skills / MCP)."""

from __future__ import annotations

import asyncio
import os
import string
import sys
from pathlib import Path
from typing import Any

from meris.harness.paths import harness_root
from meris.harness.skills import list_skill_catalog, load_skill_content
from meris.harness.ui_config import load_skill_prefs

_SKIP_DIRS = {".git", "node_modules", ".meris", "__pycache__", ".venv", "dist", "build"}

_HARNESS_DOC_CATALOG: list[dict[str, str]] = [
    {
        "id": "concepts",
        "file": "concepts.md",
        "title": "概念：工作区与 Harness",
        "blurb": "cwd、Skill、MCP、Rule 边界（改 UI 前必读）",
    },
    {
        "id": "multi-repo",
        "file": "multi-repo.md",
        "title": "多仓库任务范围",
        "blurb": "task scope、ask/plan/run 跨项目流程",
    },
    {
        "id": "readme",
        "file": "README.md",
        "title": "Harness 索引",
        "blurb": "docs/harness 入口与快速参考",
    },
    {
        "id": "architecture",
        "file": "architecture.md",
        "title": "仓库架构",
        "blurb": "包布局、CLI、import 约定",
    },
    {
        "id": "routing",
        "file": "routing.md",
        "title": "模型路由",
        "blurb": "意图 → mode → model 决策表",
    },
    {
        "id": "events",
        "file": "events.md",
        "title": "事件流 JSONL",
        "blurb": "Agent Window / --event-stream 协议",
    },
    {
        "id": "testing",
        "file": "testing.md",
        "title": "测试与 DoD",
        "blurb": "pytest · harness check · benchmark",
    },
    {
        "id": "plan-format",
        "file": "plan-format.md",
        "title": "Plan 格式",
        "blurb": "`- [ ]` checkbox 任务清单",
    },
    {
        "id": "sandbox",
        "file": "sandbox.md",
        "title": "Bash 沙箱",
        "blurb": "warn / strict · bubblewrap",
    },
]


def _harness_docs_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "harness"


def workspace_label(cwd: Path) -> str:
    return cwd.name or str(cwd)


def browse_directories(abs_path: str = "") -> dict[str, Any]:
    """Absolute-path folder browser for standalone UI (localhost only)."""
    if not (abs_path or "").strip():
        if sys.platform == "win32":
            entries = [
                {"name": f"{letter}:\\", "path": f"{letter}:\\", "isDir": True}
                for letter in string.ascii_uppercase
                if Path(f"{letter}:\\").is_dir()
            ]
            home = str(Path.home())
            entries.insert(0, {"name": "用户文件夹", "path": home, "isDir": True})
            return {"path": "", "label": "此电脑", "entries": entries, "canSelect": False}
        return browse_directories(str(Path.home()))

    raw = abs_path.strip().strip('"')
    try:
        current = Path(raw).expanduser().resolve()
    except OSError:
        current = Path.home().resolve()

    if not current.is_dir():
        parent = current.parent
        return browse_directories(str(parent) if parent.is_dir() else str(Path.home()))

    entries: list[dict[str, Any]] = []
    parent = current.parent
    if str(parent) != str(current):
        entries.append({"name": "上级目录 ..", "path": str(parent), "isDir": True, "isParent": True})

    try:
        names = sorted(os.listdir(current), key=lambda s: s.lower())
    except OSError:
        names = []
    for name in names:
        full = current / name
        try:
            if full.is_dir():
                entries.append({"name": name, "path": str(full.resolve()), "isDir": True})
        except OSError:
            continue
        if len(entries) > 160:
            break

    return {
        "path": str(current),
        "label": str(current),
        "entries": entries,
        "canSelect": True,
    }


def list_dir_entries(cwd: Path, rel: str = "") -> list[dict[str, Any]]:
    """One directory level for lazy file tree."""
    base = (cwd / rel).resolve() if rel else cwd.resolve()
    root = cwd.resolve()
    if not str(base).startswith(str(root)):
        raise ValueError("path escapes workspace")
    if not base.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    try:
        names = sorted(os.listdir(base), key=lambda s: s.lower())
    except OSError:
        return []
    for name in names:
        if name in _SKIP_DIRS and not rel:
            continue
        full = base / name
        rel_path = full.relative_to(root).as_posix()
        is_dir = full.is_dir()
        entries.append({"name": name, "path": rel_path, "isDir": is_dir})
    entries.sort(key=lambda e: (not e["isDir"], e["name"].lower()))
    return entries


def list_skills_for_ui(cwd: Path) -> list[dict[str, str | bool]]:
    return list_skill_catalog(cwd)


def skill_prefs_for_ui(cwd: Path) -> dict[str, object]:
    return load_skill_prefs(cwd)


def read_skill_for_ui(cwd: Path, name: str) -> dict[str, str] | None:
    content = load_skill_content(cwd, name)
    if content is None:
        return None
    return {"path": f".meris/skills/{name}.md", "content": content[:12000], "skill": name}


def list_harness_docs_for_ui() -> list[dict[str, str]]:
    """Curated harness doc index for Agent Window settings."""
    rows: list[dict[str, str]] = []
    base = _harness_docs_dir()
    for entry in _HARNESS_DOC_CATALOG:
        fp = base / entry["file"]
        rows.append(
            {
                "id": entry["id"],
                "title": entry["title"],
                "blurb": entry["blurb"],
                "path": f"docs/harness/{entry['file']}",
                "available": str(fp.is_file()).lower(),
            }
        )
    return rows


def read_harness_doc_for_ui(doc_id: str) -> dict[str, str] | None:
    entry = next((d for d in _HARNESS_DOC_CATALOG if d["id"] == doc_id), None)
    if not entry:
        return None
    fp = _harness_docs_dir() / entry["file"]
    if not fp.is_file():
        return None
    return {
        "id": entry["id"],
        "title": entry["title"],
        "path": f"docs/harness/{entry['file']}",
        "content": fp.read_text(encoding="utf-8")[:24000],
    }


async def _probe_mcp_connections_async(cwd: Path) -> dict[str, dict[str, Any]]:
    from meris.harness.ui_config import get_effective_mcp_servers

    servers = get_effective_mcp_servers(cwd)
    out: dict[str, dict[str, Any]] = {}
    if not servers:
        return out
    try:
        from meris.tools.mcp import MCP_AVAILABLE, MCPManager
    except ImportError:
        MCP_AVAILABLE = False  # type: ignore[misc, unused-ignore]

    if not MCP_AVAILABLE:
        for name in servers:
            out[name] = {"status": "unavailable", "detail": "pip install meris-agent[mcp]"}
        return out

    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        if cfg.get("disabled") or cfg.get("enabled") is False:
            out[name] = {"status": "disabled", "detail": "已禁用"}
            continue
        clean_cfg = {k: v for k, v in cfg.items() if k not in ("enabled", "disabled")}
        try:
            mgr, notes = await asyncio.wait_for(
                MCPManager.connect({name: clean_cfg}),
                timeout=12.0,
            )
            if name in mgr.servers:
                conn = mgr.servers[name]
                out[name] = {
                    "status": "ok",
                    "detail": f"{len(conn.tools)} tools",
                    "toolCount": len(conn.tools),
                }
            else:
                hint = next((n for n in notes if name in n), "连接失败")
                out[name] = {"status": "fail", "detail": hint[:160]}
            await mgr.close()
        except TimeoutError:
            out[name] = {"status": "fail", "detail": "连接超时"}
        except Exception as exc:
            out[name] = {"status": "fail", "detail": str(exc)[:160]}
    return out


def probe_mcp_connections_for_ui(cwd: Path) -> dict[str, dict[str, Any]]:
    try:
        return asyncio.run(_probe_mcp_connections_async(cwd))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_probe_mcp_connections_async(cwd))
        finally:
            loop.close()


def list_mcp_for_ui(cwd: Path, *, probe: bool = False) -> dict[str, Any]:
    from meris.harness.ui_config import list_mcp_servers_for_ui, mcp_config_source

    items = list_mcp_servers_for_ui(cwd)
    source = mcp_config_source(cwd)
    if probe:
        statuses = probe_mcp_connections_for_ui(cwd)
        for item in items:
            st = statuses.get(item["name"], {})
            item["connection"] = st.get("status", "unknown")
            item["connectionDetail"] = st.get("detail", "")
    return {"servers": items, "configured": bool(items), "source": source}


def list_rules_for_ui(cwd: Path) -> list[dict[str, str]]:
    rules_dir = harness_root(cwd) / "rules"
    if not rules_dir.is_dir():
        return []
    rows: list[dict[str, str]] = []
    for rp in sorted(rules_dir.glob("*.md")):
        rows.append({"name": rp.stem, "path": f".meris/rules/{rp.name}"})
    return rows


def read_rule_for_ui(cwd: Path, name: str) -> dict[str, str] | None:
    safe = name.replace("..", "").strip("/\\")
    if not safe:
        return None
    p = harness_root(cwd) / "rules" / f"{safe}.md"
    if not p.is_file():
        return None
    return {"name": safe, "path": f".meris/rules/{safe}.md", "content": p.read_text(encoding="utf-8")[:12000]}


def list_models_for_ui(cwd: Path) -> dict[str, Any]:
    from meris.harness.settings import load_settings

    models = load_settings(cwd).get("models") or {}
    by_mode = models.get("byMode") or {}
    default = models.get("default") or {}
    rules = models.get("rules") or []
    rule_rows = []
    if isinstance(rules, list):
        for r in rules:
            if isinstance(r, dict):
                rule_rows.append(
                    {
                        "name": str(r.get("name") or ""),
                        "model": str(r.get("model") or ""),
                        "profile": str(r.get("profile") or ""),
                    }
                )
    return {
        "defaultModel": str(default.get("model") or "auto"),
        "byMode": {str(k): str((v or {}).get("model") or "") for k, v in by_mode.items() if isinstance(v, dict)},
        "rules": rule_rows,
    }


_MAX_CONTEXT_IMAGE_BYTES = 8 * 1024 * 1024
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def save_context_image_for_ui(cwd: Path, *, data_url: str, filename: str = "") -> dict[str, str]:
    """Persist pasted/uploaded image under .meris/context/images/ for composer context."""
    import base64
    import re
    from datetime import UTC, datetime

    m = re.match(r"data:image/([\w+-]+);base64,(.+)", data_url, re.DOTALL)
    if not m:
        raise ValueError("invalid image data URL")
    ext_map = {"png": ".png", "jpeg": ".jpg", "jpg": ".jpg", "gif": ".gif", "webp": ".webp"}
    ext = ext_map.get(m.group(1).lower(), ".png")
    raw = base64.b64decode(m.group(2), validate=True)
    if len(raw) > _MAX_CONTEXT_IMAGE_BYTES:
        raise ValueError("image too large")
    safe = re.sub(r"[^\w.\-]+", "_", (filename or "paste").strip())[:40] or "paste"
    if Path(safe).suffix.lower() not in _IMAGE_EXT:
        safe = f"{safe}{ext}"
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    rel_dir = ".meris/context/images"
    out_dir = cwd / rel_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    rel = f"{rel_dir}/{ts}-{safe}"
    (cwd / rel).write_bytes(raw)
    rel_posix = rel.replace("\\", "/")
    return {
        "kind": "image",
        "path": rel_posix,
        "content": f"[Image attached at {rel_posix}]",
    }


def list_cli_commands_for_ui() -> dict[str, Any]:
    """Grouped CLI reference for Agent Window (settings → 命令)."""
    import json

    from meris.ui.cli_runner import RUNNABLE_CLI

    catalog = Path(__file__).resolve().parent / "static" / "cli-commands.json"
    try:
        data = json.loads(catalog.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"groups": []}
    if not isinstance(data, dict):
        return {"groups": []}
    runnable = set(RUNNABLE_CLI)
    groups = data.get("groups") if isinstance(data.get("groups"), list) else []
    for group in groups:
        if not isinstance(group, dict):
            continue
        cmds = group.get("commands")
        if not isinstance(cmds, list):
            continue
        for cmd in cmds:
            if isinstance(cmd, dict) and cmd.get("id") in runnable:
                cmd["runnable"] = True
    data["groups"] = groups
    return data
