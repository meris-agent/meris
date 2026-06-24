"""Environment contract — load `.meris/environments/*.yaml` for Agent context."""

from __future__ import annotations

from pathlib import Path

from meris.harness.paths import harness_root


def environments_dir(workspace: Path) -> Path:
    return harness_root(workspace) / "environments"


def list_environment_contracts(workspace: Path) -> list[Path]:
    d = environments_dir(workspace)
    if not d.is_dir():
        return []
    return sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml"))


def _yaml_scalar_block(text: str, key: str) -> str:
    """Best-effort extract a top-level key value from simple YAML (no PyYAML dep)."""
    lines = text.splitlines()
    capture = False
    buf: list[str] = []
    for line in lines:
        if line.startswith(f"{key}:"):
            rest = line.split(":", 1)[1].strip()
            if rest in (">", "|"):
                capture = True
                continue
            if rest:
                return rest.strip("'\"")
            capture = True
            continue
        if capture:
            if line and not line.startswith(" ") and ":" in line and not line.startswith("#"):
                break
            if line.strip():
                buf.append(line.strip())
    return " ".join(buf)[:500]


def load_environment_for_prompt(workspace: Path, *, max_chars: int = 3500) -> str:
    """Summarize environment contracts for system prompt."""
    files = list_environment_contracts(workspace)
    if not files:
        return ""
    parts: list[str] = [
        "Active environment contracts (follow blocked_actions and budget):",
    ]
    for fp in files[:3]:
        text = fp.read_text(encoding="utf-8", errors="replace")
        name = _yaml_scalar_block(text, "name") or fp.stem
        goal = _yaml_scalar_block(text, "goal")
        parts.append(f"\n### {name} (`{fp.relative_to(workspace.resolve())}`)")
        if goal:
            parts.append(f"Goal: {goal}")
        for key in ("blocked_actions", "evaluators", "budget", "human_handoff"):
            if f"{key}:" in text:
                snippet = _yaml_scalar_block(text, key)
                if snippet:
                    parts.append(f"- {key}: {snippet[:200]}")
    body = "\n".join(parts)
    return body[:max_chars]
