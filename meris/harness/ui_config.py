"""Agent Window UI persistence — MCP & harness picks (not settings.yaml)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from meris.harness.paths import harness_root

_SKILL_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
_UI_DIR = "ui"
_MCP_FILE = "mcp-servers.json"
_SKILL_PREFS_FILE = "skill-prefs.json"
_ROOTS_FILE = "workspace-roots.json"
_STALE_PYTEST_ROOT = re.compile(r"[/\\]pytest-\d+[/\\]test_[^/\\]+[/\\]", re.I)


def _is_stale_pytest_workspace_root(path: Path) -> bool:
    """Drop pytest tmp_path leaves (a/b) left in global ~/.meris/ui/workspace-roots.json."""
    norm = str(path).replace("\\", "/").lower()
    if "pytest-of-" not in norm:
        return False
    if "/temp/pytest-of-" not in norm and "/tmp/pytest-of-" not in norm:
        return False
    if not _STALE_PYTEST_ROOT.search(norm):
        return False
    parts = path.parts
    for j in range(len(parts) - 1, -1, -1):
        if re.match(r"test_.+\d+$", parts[j], re.I):
            tail = parts[j + 1 :]
            return len(tail) == 1 and tail[0] in ("a", "b")
    return False


def _mcp_path(workspace: Path) -> Path:
    return harness_root(workspace) / _UI_DIR / _MCP_FILE


def load_ui_mcp_servers_raw(workspace: Path) -> dict[str, Any] | None:
    """Return UI MCP map if file exists; None if user never saved via Agent UI."""
    p = _mcp_path(workspace)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict) and "mcpServers" in data:
        raw = data["mcpServers"]
        return raw if isinstance(raw, dict) else {}
    return data if isinstance(data, dict) else {}


def save_ui_mcp_servers(workspace: Path, servers: dict[str, Any]) -> Path:
    """Persist MCP servers from Agent UI."""
    p = _mcp_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"mcpServers": servers}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _filter_enabled(servers: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        if cfg.get("enabled") is False or cfg.get("disabled"):
            continue
        clean = {k: v for k, v in cfg.items() if k not in ("enabled", "disabled")}
        out[name] = clean
    return out


def get_effective_mcp_servers(workspace: Path) -> dict[str, Any]:
    """UI file wins when present; else fall back to settings (CLI/TUI compat)."""
    ui = load_ui_mcp_servers_raw(workspace)
    if ui is not None:
        return _filter_enabled(ui)
    from meris.harness.settings import load_settings

    return load_settings(workspace).get("mcpServers") or {}


def mcp_config_source(workspace: Path) -> str:
    """``ui`` = `.meris/ui/mcp-servers.json`; ``settings`` = `.meris/settings.yaml`."""
    if load_ui_mcp_servers_raw(workspace) is not None:
        return "ui"
    return "settings"


def migrate_mcp_to_ui(workspace: Path) -> bool:
    """Copy ``settings.yaml`` ``mcpServers`` into ``.meris/ui/mcp-servers.json``."""
    if load_ui_mcp_servers_raw(workspace) is not None:
        return False
    from meris.harness.settings import load_settings

    raw = load_settings(workspace).get("mcpServers") or {}
    if not raw:
        return False
    save_ui_mcp_servers(workspace, raw)
    return True


def import_mcp_from_path(workspace: Path, file_path: Path) -> bool:
    """Import MCP from an arbitrary ``mcp.json`` file."""
    p = file_path.expanduser().resolve()
    if not p.is_file():
        return False
    try:
        servers = parse_mcp_json_text(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not servers:
        return False
    save_ui_mcp_servers(workspace, servers)
    return True


def list_mcp_servers_for_ui(workspace: Path) -> list[dict[str, Any]]:
    raw = load_ui_mcp_servers_raw(workspace)
    if raw is None:
        from meris.harness.settings import load_settings

        raw = load_settings(workspace).get("mcpServers") or {}
    items: list[dict[str, Any]] = []
    for name, cfg in (raw or {}).items():
        if not isinstance(cfg, dict):
            continue
        items.append(
            {
                "name": name,
                "enabled": cfg.get("enabled", True) is not False and not cfg.get("disabled"),
                "transport": cfg.get("transport", "stdio"),
                "command": cfg.get("command", ""),
                "args": list(cfg.get("args") or []),
                "url": cfg.get("url", ""),
                "env": dict(cfg.get("env") or {}),
            }
        )
    return sorted(items, key=lambda x: x["name"])


def mcp_servers_dict_from_ui_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    servers: dict[str, Any] = {}
    for item in items:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        servers[name] = {
            "transport": item.get("transport") or "stdio",
            "command": item.get("command") or "",
            "args": list(item.get("args") or []),
            "url": item.get("url") or "",
            "env": dict(item.get("env") or {}),
            "enabled": bool(item.get("enabled", True)),
        }
    return servers


def ui_items_to_mcp_json_text(items: list[dict[str, Any]]) -> str:
    """Cursor-compatible mcp.json snippet for the Agent UI editor."""
    servers = mcp_servers_dict_from_ui_items(items)
    clean: dict[str, Any] = {}
    for name, cfg in servers.items():
        entry: dict[str, Any] = {}
        if cfg.get("url"):
            entry["url"] = cfg["url"]
        else:
            if cfg.get("command"):
                entry["command"] = cfg["command"]
            if cfg.get("args"):
                entry["args"] = cfg["args"]
        if cfg.get("env"):
            entry["env"] = cfg["env"]
        if cfg.get("enabled") is False:
            entry["enabled"] = False
        clean[name] = entry
    return json.dumps({"mcpServers": clean}, ensure_ascii=False, indent=2)


def parse_mcp_json_text(text: str) -> dict[str, Any]:
    """Parse Cursor-style mcp.json body into server map."""
    data = json.loads(text)
    if isinstance(data, dict) and "mcpServers" in data:
        raw = data["mcpServers"]
        return raw if isinstance(raw, dict) else {}
    return data if isinstance(data, dict) else {}


def mcp_json_to_ui_items(servers: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for name, cfg in (servers or {}).items():
        if not isinstance(cfg, dict):
            continue
        transport = "sse" if cfg.get("url") else "stdio"
        items.append(
            {
                "name": name,
                "enabled": cfg.get("enabled", True) is not False and not cfg.get("disabled"),
                "transport": cfg.get("transport", transport),
                "command": cfg.get("command", ""),
                "args": list(cfg.get("args") or []),
                "url": cfg.get("url", ""),
                "env": dict(cfg.get("env") or {}),
            }
        )
    return sorted(items, key=lambda x: x["name"])


def load_cursor_mcp_json(workspace: Path) -> dict[str, Any] | None:
    p = workspace / ".cursor" / "mcp.json"
    if not p.is_file():
        return None
    try:
        return parse_mcp_json_text(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


_RULE_NAME_RE = _SKILL_NAME_RE


def save_rule(workspace: Path, name: str, content: str) -> Path:
    if not _RULE_NAME_RE.match(name):
        raise ValueError("rule name must be alphanumeric/underscore/dash")
    p = harness_root(workspace) / "rules" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = content.strip()
    if not body:
        body = f"# {name}\n"
    p.write_text(body + ("\n" if not body.endswith("\n") else ""), encoding="utf-8")
    return p


def import_cursor_rules(workspace: Path) -> int:
    """Copy .cursor/rules/*.md(c) into .meris/rules/; returns count imported."""
    return import_rules_from_dir(workspace, workspace / ".cursor" / "rules")


def import_rules_from_dir(workspace: Path, src: Path) -> int:
    """Copy ``*.md`` / ``*.mdc`` from *src* into ``.meris/rules/``."""
    src = src.expanduser().resolve()
    if not src.is_dir():
        return 0
    dst = harness_root(workspace) / "rules"
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for rp in sorted(src.iterdir()):
        if not rp.is_file():
            continue
        if rp.suffix not in (".md", ".mdc"):
            continue
        name = rp.stem
        if not _RULE_NAME_RE.match(name):
            continue
        text = rp.read_text(encoding="utf-8")
        if rp.suffix == ".mdc" and not text.startswith("---"):
            text = f"---\nsource: cursor\n---\n\n{text}"
        (dst / f"{name}.md").write_text(text, encoding="utf-8")
        count += 1
    return count


def save_skill(workspace: Path, name: str, content: str) -> Path:
    if not _SKILL_NAME_RE.match(name):
        raise ValueError("skill name must be alphanumeric/underscore/dash")
    p = harness_root(workspace) / "skills" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = content.strip()
    if not body:
        body = f"# {name}\n"
    p.write_text(body + ("\n" if not body.endswith("\n") else ""), encoding="utf-8")
    return p


def save_global_skill(name: str, content: str) -> Path:
    if not _SKILL_NAME_RE.match(name):
        raise ValueError("skill name must be alphanumeric/underscore/dash")
    from meris.harness.skills import global_skills_dir

    d = global_skills_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    body = content.strip()
    if not body:
        body = f"# {name}\n"
    p.write_text(body + ("\n" if not body.endswith("\n") else ""), encoding="utf-8")
    return p


def install_bundled_to_global(name: str) -> Path | None:
    if not _SKILL_NAME_RE.match(name):
        raise ValueError("skill name must be alphanumeric/underscore/dash")
    from meris.harness.skills import _pkg_skills_dir, global_skills_dir

    src = _pkg_skills_dir() / f"{name}.md"
    if not src.is_file():
        return None
    d = global_skills_dir()
    d.mkdir(parents=True, exist_ok=True)
    dst = d / f"{name}.md"
    if not dst.is_file():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def _skill_prefs_path(workspace: Path) -> Path:
    return harness_root(workspace) / _UI_DIR / _SKILL_PREFS_FILE


def load_skill_prefs(workspace: Path) -> dict[str, Any]:
    p = _skill_prefs_path(workspace)
    if not p.is_file():
        return {"disabled": [], "importSourcePath": ""}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"disabled": [], "importSourcePath": ""}
    if not isinstance(data, dict):
        return {"disabled": [], "importSourcePath": ""}
    disabled = data.get("disabled")
    if not isinstance(disabled, list):
        disabled = []
    return {
        "disabled": [str(x) for x in disabled],
        "importSourcePath": str(data.get("importSourcePath") or "").strip(),
    }


def save_skill_prefs(workspace: Path, prefs: dict[str, Any]) -> None:
    p = _skill_prefs_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    disabled = prefs.get("disabled") if isinstance(prefs.get("disabled"), list) else []
    out = {
        "disabled": sorted({str(x) for x in disabled}),
        "importSourcePath": str(prefs.get("importSourcePath") or "").strip(),
    }
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_skill_import_source(workspace: Path, path: str) -> None:
    prefs = load_skill_prefs(workspace)
    if path and str(path).strip():
        prefs["importSourcePath"] = str(Path(path).expanduser().resolve())
    else:
        prefs["importSourcePath"] = ""
    save_skill_prefs(workspace, prefs)


def default_skill_import_dirs(workspace: Path) -> list[Path]:
    return [
        workspace / ".agents" / "skills",
        workspace / ".cursor" / "skills",
    ]


def resolve_skill_import_source(workspace: Path, explicit: str | None = None) -> Path | None:
    if explicit and str(explicit).strip():
        p = Path(str(explicit).strip()).expanduser().resolve()
        return p if p.is_dir() else None
    prefs = load_skill_prefs(workspace)
    saved = str(prefs.get("importSourcePath") or "").strip()
    if saved:
        p = Path(saved).expanduser().resolve()
        if p.is_dir():
            return p
    for d in default_skill_import_dirs(workspace):
        if d.is_dir():
            return d
    return None


def import_skills_from_dir(workspace: Path, src: Path) -> int:
    """Copy skills from *src* into ``.meris/skills/``; returns count imported."""
    if not src.is_dir():
        return 0
    dst = harness_root(workspace) / "skills"
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for entry in sorted(src.iterdir()):
        if entry.is_dir():
            skill_md = entry / "SKILL.md"
            if not skill_md.is_file():
                continue
            name = entry.name
            if not _SKILL_NAME_RE.match(name):
                continue
            text = skill_md.read_text(encoding="utf-8")
            if not text.startswith("---"):
                text = f"---\nsource: import\n---\n\n{text}"
            elif "source:" not in text.split("---", 2)[1]:
                text = text.replace("---\n", "---\nsource: import\n", 1)
            (dst / f"{name}.md").write_text(text, encoding="utf-8")
            count += 1
        elif entry.is_file() and entry.suffix == ".md":
            name = entry.stem
            if not _SKILL_NAME_RE.match(name):
                continue
            text = entry.read_text(encoding="utf-8")
            (dst / entry.name).write_text(text, encoding="utf-8")
            count += 1
    return count


def import_cursor_skills(workspace: Path) -> int:
    """Import from saved source path or default project skill directories."""
    src = resolve_skill_import_source(workspace)
    if not src:
        return 0
    return import_skills_from_dir(workspace, src)


def set_skill_enabled(workspace: Path, name: str, enabled: bool) -> None:
    if not _SKILL_NAME_RE.match(name):
        raise ValueError("skill name must be alphanumeric/underscore/dash")
    prefs = load_skill_prefs(workspace)
    disabled = set(prefs.get("disabled") or [])
    if enabled:
        disabled.discard(name)
    else:
        disabled.add(name)
    prefs["disabled"] = sorted(disabled)
    save_skill_prefs(workspace, prefs)


def install_bundled_skill(workspace: Path, name: str) -> Path | None:
    if not _SKILL_NAME_RE.match(name):
        raise ValueError("skill name must be alphanumeric/underscore/dash")
    from meris.harness.skills import _pkg_skills_dir

    src = _pkg_skills_dir() / f"{name}.md"
    if not src.is_file():
        return None
    dst = harness_root(workspace) / "skills" / f"{name}.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.is_file():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def is_meris_repo_root(path: Path) -> bool:
    """Heuristic: meris Python package or harness at repo root."""
    p = path.resolve()
    if (p / ".meris").is_dir():
        return True
    if (p / "pyproject.toml").is_file() and (p / "meris").is_dir():
        return True
    return False


def _is_skill_or_template_root(path: Path) -> bool:
    """Skill 目录不是项目根 — 不应出现在 cwd / 左栏项目列表。"""
    norm = str(path).replace("\\", "/").lower()
    if "/.system/" in norm or norm.endswith("/.system"):
        return True
    for marker in (
        "/.cursor/skills/",
        "/templates/skills/",
        "/.meris/skills/",
        "/.agents/skills/",
    ):
        if marker in norm:
            return True
    try:
        global_skills = (Path.home() / ".meris" / "skills").resolve()
        if path.resolve() == global_skills:
            return True
    except OSError:
        pass
    if (path / "SKILL.md").is_file() and not is_meris_repo_root(path):
        return True
    return False


def is_valid_workspace_root(path: Path) -> bool:
    """True when *path* is a plausible Agent project cwd (not a Skill folder)."""
    try:
        p = path.expanduser().resolve()
    except OSError:
        return False
    if not p.is_dir():
        return False
    if _is_skill_or_template_root(p):
        return False
    return True


def find_meris_roots(search_roots: list[Path]) -> list[Path]:
    """Collect meris repo paths (root or subfolder meris/), meris first."""
    seen: set[str] = set()
    meris: list[Path] = []
    other: list[Path] = []
    for root in search_roots:
        root = root.resolve()
        key = str(root)
        if key not in seen:
            seen.add(key)
            (meris if is_meris_repo_root(root) else other).append(root)
        sub = root / "meris"
        sub_key = str(sub)
        if sub.is_dir() and sub_key not in seen and is_meris_repo_root(sub):
            seen.add(sub_key)
            meris.append(sub)
    return meris + other


def _global_ui_dir() -> Path:
    return Path.home() / ".meris" / _UI_DIR


def _roots_file() -> Path:
    return _global_ui_dir() / _ROOTS_FILE


def load_workspace_roots(*, rewrite: bool = False) -> list[Path]:
    """User-level persisted workspace roots (meris ui standalone)."""
    p = _roots_file()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw = data.get("roots") if isinstance(data, dict) else []
    if not isinstance(raw, list):
        return []
    out: list[Path] = []
    seen: set[str] = set()
    dropped = 0
    for item in raw:
        try:
            path = Path(str(item)).expanduser().resolve()
        except OSError:
            dropped += 1
            continue
        key = str(path)
        if key in seen:
            dropped += 1
            continue
        if not path.is_dir() or not is_valid_workspace_root(path):
            dropped += 1
            continue
        seen.add(key)
        out.append(path)
    if rewrite and dropped and p.is_file():
        save_workspace_roots(out)
    return out


def prune_workspace_roots() -> tuple[list[Path], int]:
    """Remove missing/stale-pytest/duplicate roots; returns (kept, removed_count)."""
    p = _roots_file()
    if not p.is_file():
        return [], 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], 0
    raw = data.get("roots") if isinstance(data, dict) else []
    if not isinstance(raw, list):
        return [], 0
    before = len(raw)
    kept: list[Path] = []
    seen: set[str] = set()
    for item in raw:
        try:
            path = Path(str(item)).expanduser().resolve()
        except OSError:
            continue
        key = str(path)
        if key in seen:
            continue
        if not path.is_dir() or _is_stale_pytest_workspace_root(path):
            continue
        if not is_valid_workspace_root(path):
            continue
        seen.add(key)
        kept.append(path)
    save_workspace_roots(kept)
    return kept, max(0, before - len(kept))


def save_workspace_roots(roots: list[Path]) -> Path:
    p = _roots_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    unique: list[str] = []
    seen: set[str] = set()
    for root in roots:
        try:
            key = str(root.expanduser().resolve())
        except OSError:
            continue
        if key not in seen:
            seen.add(key)
            unique.append(key)
    p.write_text(json.dumps({"roots": unique}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def add_workspace_root(path: Path) -> tuple[list[Path], bool]:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError("not a directory")
    if not is_valid_workspace_root(resolved):
        raise ValueError("skill or system paths cannot be workspace roots — use Settings → Skills")
    roots = load_workspace_roots()
    key = str(resolved)
    if any(str(r) == key for r in roots):
        return roots, False
    roots.append(resolved)
    save_workspace_roots(roots)
    return roots, True


def remove_workspace_root(path: Path) -> list[Path]:
    key = str(path.expanduser().resolve())
    roots = [r for r in load_workspace_roots() if str(r) != key]
    save_workspace_roots(roots)
    return roots


def pick_plan_execute_root(active_cwd: Path) -> Path:
    """Pick workspace root for plan execution (prefer nested meris repo)."""
    active = active_cwd.expanduser().resolve()
    folders = collect_workspace_folders(active)
    paths = [Path(f["path"]) for f in folders]
    related: list[Path] = []
    for p in paths:
        try:
            if p == active or p.is_relative_to(active) or active.is_relative_to(p):
                related.append(p)
        except ValueError:
            continue
    if not related:
        related = [active]

    meris_roots = [p for p in related if is_meris_repo_root(p)]
    if not meris_roots:
        return active

    for candidate in meris_roots:
        for parent in related:
            if parent == candidate:
                continue
            try:
                if candidate.is_relative_to(parent):
                    return candidate
            except ValueError:
                continue

    for candidate in meris_roots:
        if candidate == active:
            return active
    return meris_roots[0]


def plan_payload_for_workspace(workspace: Path) -> dict[str, object] | None:
    """Load plan checkbox state for Agent Window, if tasks.md exists."""
    from meris.harness.plan import parse_plan_checkboxes

    plan_file = harness_root(workspace) / "plan" / "tasks.md"
    if not plan_file.is_file():
        return None
    try:
        rel = str(plan_file.relative_to(workspace.resolve()))
    except ValueError:
        rel = ".meris/plan/tasks.md"
    return {
        "path": rel,
        "items": parse_plan_checkboxes(plan_file.read_text(encoding="utf-8")),
    }


def collect_workspace_folders(active_cwd: Path) -> list[dict[str, str]]:
    """Merge persisted roots + active cwd, expanded via find_meris_roots."""
    seen_paths: set[str] = set()
    meris_entries: list[dict[str, str]] = []
    other_entries: list[dict[str, str]] = []

    seed_roots: list[Path] = []
    seed_seen: set[str] = set()
    active = active_cwd.expanduser().resolve()
    for candidate in [*load_workspace_roots(), active]:
        if not candidate.is_dir():
            continue
        if not is_valid_workspace_root(candidate):
            continue
        key = str(candidate)
        if key in seed_seen:
            continue
        seed_seen.add(key)
        seed_roots.append(candidate)

    for root in seed_roots:
        for p in find_meris_roots([root]):
            key = str(p)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            entry = {"name": p.name, "path": key}
            (meris_entries if is_meris_repo_root(p) else other_entries).append(entry)

    return meris_entries + other_entries
