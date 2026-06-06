"""Static harness checks — mechanical enforcement (Phase E2)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_BAD_IMPORT = re.compile(r"^\s*(?:from|import)\s+forge\b", re.M)
_BAD_README_PATH = re.compile(r"(?<![\w-])meris/README\.md", re.I)
_DOC_README_SKIP = re.compile(
    r"不要|不是|禁止|don't|do not|\bnot\b|not use|写错|写成|错误|典型|dogfood|复盘|不要用",
    re.I,
)
_CHECK_MD_GLOBS = ("README.md", "AGENTS.md", "PROGRESS.md")


@dataclass
class HarnessCheckResult:
    name: str
    ok: bool
    detail: str
    hint: str = ""


def run_harness_check(workspace: Path) -> list[HarnessCheckResult]:
    ws = workspace.resolve()
    results: list[HarnessCheckResult] = []

    agents = ws / "AGENTS.md"
    if agents.is_file():
        results.append(HarnessCheckResult("AGENTS.md", True, "present"))
    else:
        results.append(
            HarnessCheckResult(
                "AGENTS.md",
                False,
                "missing",
                hint="Run: meris init-harness .",
            )
        )

    docs_index = ws / "docs" / "harness" / "README.md"
    if docs_index.is_file():
        results.append(HarnessCheckResult("docs/harness", True, "present"))
    else:
        results.append(
            HarnessCheckResult(
                "docs/harness",
                True,
                "optional — add docs/harness/ for progressive disclosure",
            )
        )

    pkg = ws / "meris"
    if pkg.is_dir():
        bad_files: list[str] = []
        for py in pkg.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            text = py.read_text(encoding="utf-8", errors="replace")
            rel = py.relative_to(ws).as_posix()
            if _BAD_IMPORT.search(text):
                bad_files.append(rel)

        if bad_files:
            results.append(
                HarnessCheckResult(
                    "import:forge",
                    False,
                    ", ".join(bad_files[:5]),
                    hint="Use `from meris....` — see docs/harness/architecture.md",
                )
            )
        else:
            results.append(HarnessCheckResult("import:forge", True, "no forge/ imports"))

        readme_hits: list[str] = []
        for name in _CHECK_MD_GLOBS:
            fp = ws / name
            if not fp.is_file():
                continue
            for i, line in enumerate(fp.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if _BAD_README_PATH.search(line) and not _DOC_README_SKIP.search(line):
                    readme_hits.append(f"{name}:{i}")
                    break
        plan = ws / ".meris" / "plan" / "tasks.md"
        if plan.is_file():
            for i, line in enumerate(plan.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if _BAD_README_PATH.search(line) and not _DOC_README_SKIP.search(line):
                    readme_hits.append(f".meris/plan/tasks.md:{i}")
                    break
        if readme_hits:
            results.append(
                HarnessCheckResult(
                    "paths:readme",
                    False,
                    ", ".join(readme_hits),
                    hint="Use `README.md` at repo root — see .meris/rules/paths.md",
                )
            )
        else:
            results.append(HarnessCheckResult("paths:readme", True, "no meris/README.md"))

    return results


def harness_check_failed(results: list[HarnessCheckResult]) -> bool:
    return any(not r.ok for r in results)


def format_check_summary(results: list[HarnessCheckResult]) -> str:
    lines: list[str] = []
    for r in results:
        if r.ok:
            lines.append(f"{r.name}: ok — {r.detail}")
        else:
            lines.append(f"{r.name}: FAIL — {r.detail}")
            if r.hint:
                lines.append(f"  hint: {r.hint}")
    return "\n".join(lines)


def is_harness_check_failure(text: str) -> bool:
    lower = text.lower()
    return (
        "import:forge" in lower
        or "paths:readme" in lower
        or "harness check" in lower
        or "meris/readme" in lower
    )
