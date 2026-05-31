"""Kiro-style spec workflow — requirements → design → tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from meris.harness.paths import harness_root

SPEC_FILES = {
    "requirements": "requirements.md",
    "design": "design.md",
    "tasks": "tasks.md",
}

PHASE_ORDER = ("requirements", "design", "tasks")

SPEC_PROMPTS = {
    "requirements": (
        "Draft requirements for this feature. Use EARS-style acceptance criteria "
        "(- [ ] WHEN ... THE SYSTEM SHALL ...). Include user story and out of scope."
    ),
    "design": (
        "Draft technical design based on existing requirements.md in spec context. "
        "Include overview, components, data flow, and risks. Markdown only."
    ),
    "tasks": (
        "Draft an implementation task checklist based on requirements and design. "
        "Use - [ ] items grouped by phase. Include verification steps."
    ),
}

STATE_FILE = "state.json"


def spec_dir(workspace: Path) -> Path:
    return harness_root(workspace) / "spec"


def _state_path(workspace: Path) -> Path:
    return spec_dir(workspace) / STATE_FILE


def _is_phase_incomplete(text: str) -> bool:
    t = text.strip()
    if len(t) < 100:
        return True
    if "(TBD)" in t:
        return True
    return False


@dataclass
class SpecPhase:
    name: str
    path: Path
    prompt: str


def load_state(workspace: Path) -> dict:
    p = _state_path(workspace)
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(workspace: Path, state: dict) -> None:
    d = spec_dir(workspace)
    d.mkdir(parents=True, exist_ok=True)
    _state_path(workspace).write_text(json.dumps(state, indent=2), encoding="utf-8")


def init_spec(workspace: Path, feature: str, *, tpl_dir: Path | None = None) -> Path:
    d = spec_dir(workspace)
    d.mkdir(parents=True, exist_ok=True)
    tpl = tpl_dir or Path(__file__).resolve().parents[2] / "templates" / "spec"
    for key, fname in SPEC_FILES.items():
        p = d / fname
        if not p.exists():
            tpl_file = tpl / fname
            if tpl_file.is_file():
                p.write_text(
                    tpl_file.read_text(encoding="utf-8").replace("{{feature}}", feature),
                    encoding="utf-8",
                )
            else:
                p.write_text(f"# {key.title()}: {feature}\n\n(TBD)\n", encoding="utf-8")
    save_state(
        workspace,
        {"feature": feature, "phase": "requirements", "completed": []},
    )
    return d


def get_next_phase(workspace: Path) -> SpecPhase | None:
    d = spec_dir(workspace)
    if not d.is_dir():
        return None
    for name in PHASE_ORDER:
        p = d / SPEC_FILES[name]
        if not p.is_file():
            return SpecPhase(name, p, SPEC_PROMPTS[name])
        if _is_phase_incomplete(p.read_text(encoding="utf-8")):
            return SpecPhase(name, p, SPEC_PROMPTS[name])
    return None


def spec_status(workspace: Path) -> list[tuple[str, str, str]]:
    """Return (phase, status, detail) for each phase."""
    d = spec_dir(workspace)
    rows: list[tuple[str, str, str]] = []
    state = load_state(workspace)
    feature = state.get("feature", "?")
    for name in PHASE_ORDER:
        p = d / SPEC_FILES[name]
        if not p.is_file():
            rows.append((name, "missing", "run meris spec init"))
            continue
        text = p.read_text(encoding="utf-8")
        if _is_phase_incomplete(text):
            rows.append((name, "pending", f"{len(text)} bytes, has TBD"))
        else:
            rows.append((name, "done", f"{len(text)} bytes"))
    rows.insert(0, ("feature", "info", feature))
    return rows


def phase_is_complete(text: str) -> bool:
    return not _is_phase_incomplete(text)


def mark_phase_complete(workspace: Path, phase: str) -> None:
    state = load_state(workspace)
    completed = list(state.get("completed") or [])
    if phase not in completed:
        completed.append(phase)
    state["completed"] = completed
    idx = PHASE_ORDER.index(phase) if phase in PHASE_ORDER else -1
    if idx >= 0 and idx + 1 < len(PHASE_ORDER):
        state["phase"] = PHASE_ORDER[idx + 1]
    else:
        state["phase"] = "done"
    save_state(workspace, state)


def load_spec_context(workspace: Path) -> str:
    d = spec_dir(workspace)
    if not d.is_dir():
        return ""
    parts = []
    for name in SPEC_FILES.values():
        p = d / name
        if p.is_file():
            parts.append(f"<!-- {name} -->\n{p.read_text(encoding='utf-8')[:6000]}")
    return "\n\n".join(parts)


def build_spec_task(phase: SpecPhase, user_note: str = "") -> str:
    base = phase.prompt
    if user_note.strip():
        base += f"\n\nAdditional context from user:\n{user_note.strip()}"
    base += f"\n\nOutput ONLY the markdown content for {phase.path.name}."
    return base
