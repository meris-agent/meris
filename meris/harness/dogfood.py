"""Daily dogfood readiness checks (Route B)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from meris.harness.check import harness_check_failed, run_harness_check


@dataclass
class DogfoodResult:
    name: str
    status: str  # ok | warn | fail
    detail: str


_OPEN_SESSION_RE = re.compile(r"Status\*\*:\s*(dod_failed|error)\s*$", re.MULTILINE)


def run_dogfood_check(cwd: Path) -> list[DogfoodResult]:
    """Lightweight checks before a real dogfood session (no live API probe)."""
    ws = cwd.resolve()
    rows: list[DogfoodResult] = []

    progress = ws / "PROGRESS.md"
    if progress.is_file():
        text = progress.read_text(encoding="utf-8", errors="replace")
        if _OPEN_SESSION_RE.search(text):
            rows.append(
                DogfoodResult(
                    "progress-sessions",
                    "warn",
                    "PROGRESS.md has open dod_failed/error session notes",
                )
            )
        else:
            rows.append(DogfoodResult("progress-sessions", "ok", "no open failed session notes"))
    else:
        rows.append(DogfoodResult("progress-sessions", "warn", "PROGRESS.md missing"))

    guide = ws / "docs" / "DOGFOOD_DAILY.md"
    rows.append(
        DogfoodResult(
            "dogfood-guide",
            "ok" if guide.is_file() else "warn",
            "docs/DOGFOOD_DAILY.md present" if guide.is_file() else "missing dogfood guide",
        )
    )

    harness = run_harness_check(ws)
    rows.append(
        DogfoodResult(
            "harness-check",
            "fail" if harness_check_failed(harness) else "ok",
            "static harness checks passed"
            if not harness_check_failed(harness)
            else "harness check failed — run meris harness check",
        )
    )

    native_loop = (os.environ.get("MERIS_NATIVE_LOOP") or "").strip()
    if native_loop:
        rows.append(DogfoodResult("native-loop-env", "ok", f"MERIS_NATIVE_LOOP={native_loop}"))
    else:
        rows.append(
            DogfoodResult(
                "native-loop-env",
                "warn",
                "MERIS_NATIVE_LOOP unset — see .env.example (recommended: auto)",
            )
        )

    return rows


def dogfood_check_failed(results: list[DogfoodResult]) -> bool:
    return any(r.status == "fail" for r in results)
