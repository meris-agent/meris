"""Project scan → harness proposals (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from meris.harness.ratchet.proposal import Proposal, ProposalTarget, list_proposals, new_proposal_id, save_proposal


@dataclass
class ProjectFacts:
    package_manager: str = "unknown"
    test_cmd: str = ""
    python_pkg: str = ""
    rust_crate: bool = False
    node_project: bool = False
    top_dirs: list[str] = field(default_factory=list)
    repo_root_markers: list[str] = field(default_factory=list)


def scan_project(workspace: Path) -> ProjectFacts:
    ws = workspace.resolve()
    facts = ProjectFacts()
    markers = []
    if (ws / "pyproject.toml").is_file():
        markers.append("pyproject.toml")
        facts.package_manager = "pip"
        facts.test_cmd = 'pytest tests/ -m "not integration" -q'
        facts.python_pkg = "meris" if (ws / "meris").is_dir() and (ws / "meris" / "__init__.py").is_file() else ""
    if (ws / "Cargo.toml").is_file():
        markers.append("Cargo.toml")
        facts.rust_crate = True
        if not facts.test_cmd:
            facts.test_cmd = "cargo test"
    if (ws / "package.json").is_file():
        markers.append("package.json")
        facts.node_project = True
        if not facts.test_cmd:
            facts.test_cmd = "npm test"

    for name in ("tests", "meris", "src", "docs", "scripts", "templates"):
        if (ws / name).is_dir():
            facts.top_dirs.append(name)
    facts.repo_root_markers = markers
    return facts


def _agents_needs_dod(agents_text: str) -> bool:
    lower = agents_text.lower()
    return "configure dod" in lower or 'echo "configure' in lower


def _lesson_pending(workspace: Path, lesson: str) -> bool:
    for p in list_proposals(workspace, status="pending"):
        if p.lesson == lesson:
            return True
    rel = workspace / ".meris" / "rules" / "project.md"
    if lesson == "L-learn-project" and rel.is_file() and "ratchet:L-learn-project" in rel.read_text(
        encoding="utf-8"
    ):
        return True
    agents = workspace / "AGENTS.md"
    if lesson == "L-learn-dod" and agents.is_file() and "ratchet:L-learn-dod" in agents.read_text(
        encoding="utf-8"
    ):
        return True
    return False


def build_learn_proposals(workspace: Path, *, init: bool = False) -> list[Proposal]:
    """Create proposals from project layout. Does not write files."""
    ws = workspace.resolve()
    facts = scan_project(ws)
    created: list[Proposal] = []

    if not facts.repo_root_markers and not init:
        return created

    layout_lines = [
        "<!-- ratchet:L-learn-project -->",
        "",
        "## 项目画像（ratchet learn）",
        "",
        f"- 包管理：**{facts.package_manager}**",
        f"- 顶层目录：{', '.join(facts.top_dirs) or '(未识别)'}",
        f"- 仓库标识：{', '.join(facts.repo_root_markers) or '(无)'}",
    ]
    if facts.python_pkg:
        layout_lines.append(f"- Python 包目录：`{facts.python_pkg}/`")
    if facts.rust_crate:
        layout_lines.append("- Rust：`meris-rs/` 或 `Cargo.toml` 所在 crate")
    if facts.test_cmd:
        layout_lines.append(f"- 建议测试：`{facts.test_cmd}`")

    if not _lesson_pending(ws, "L-learn-project"):
        created.append(
            Proposal(
                id=new_proposal_id(),
                lesson="L-learn-project",
                summary="项目画像（目录 / 包管理 / 测试命令）",
                target=ProposalTarget(
                    path=".meris/rules/project.md",
                    action="create",
                    content="\n".join(layout_lines) + "\n",
                ),
                signals=["learn:scan"],
                verify=[],
            )
        )

    agents = ws / "AGENTS.md"
    if agents.is_file() and facts.test_cmd:
        text = agents.read_text(encoding="utf-8")
        if _agents_needs_dod(text) and not _lesson_pending(ws, "L-learn-dod"):
            dod_block = f"""<!-- ratchet:L-learn-dod -->

## Ratchet (learn) — 建议 DoD

将「完成定义」中的占位命令替换为：

- `{facts.test_cmd}`
"""
            created.append(
                Proposal(
                    id=new_proposal_id(),
                    lesson="L-learn-dod",
                    summary="AGENTS.md DoD 仍为占位，建议填入真实测试命令",
                    target=ProposalTarget(
                        path="AGENTS.md",
                        action="append",
                        content=dod_block,
                    ),
                    confidence="medium",
                    signals=["learn:agents-dod"],
                    verify=[facts.test_cmd],
                )
            )

    return created


def run_learn(
    workspace: Path,
    *,
    init: bool = False,
    save: bool = True,
) -> list[Proposal]:
    props = build_learn_proposals(workspace, init=init)
    if save:
        for p in props:
            save_proposal(workspace, p)
    return props
