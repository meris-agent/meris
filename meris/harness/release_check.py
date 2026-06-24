"""Release readiness checks (E0) — no tag/PyPI upload."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReleaseCheck:
    name: str
    status: str  # ok | warn | fail
    detail: str


def _run(cmd: list[str], *, cwd: Path, timeout: int = 300) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, out[-500:] if len(out) > 500 else out


def run_release_checks(repo_root: Path) -> list[ReleaseCheck]:
    """Checks runnable before tagging v0.0.1 (no network publish)."""
    root = repo_root.resolve()
    checks: list[ReleaseCheck] = []

    code, out = _run(
        [sys.executable, "-m", "pytest", "tests/", "-m", "not integration", "-q"],
        cwd=root,
    )
    checks.append(
        ReleaseCheck(
            "pytest",
            "ok" if code == 0 else "fail",
            "unit tests green" if code == 0 else out or f"exit {code}",
        )
    )

    code, out = _run([sys.executable, "scripts/run_benchmark_mock.py"], cwd=root)
    checks.append(
        ReleaseCheck(
            "benchmark mock",
            "ok" if code == 0 else "fail",
            "8/8 offline" if code == 0 else out or f"exit {code}",
        )
    )

    code, out = _run([sys.executable, "-m", "meris", "harness", "check", "--cwd", str(root)], cwd=root)
    checks.append(
        ReleaseCheck(
            "harness check",
            "ok" if code == 0 else "fail",
            "static harness ok" if code == 0 else out or f"exit {code}",
        )
    )

    code, out = _run([sys.executable, "-m", "meris", "ratchet", "status", "--cwd", str(root)], cwd=root)
    checks.append(
        ReleaseCheck(
            "ratchet status",
            "ok" if code == 0 else "warn",
            "ok" if code == 0 else out or f"exit {code}",
        )
    )

    try:
        from importlib.metadata import version

        ver = version("meris-agent")
        checks.append(ReleaseCheck("package version", "ok", f"meris-agent {ver}"))
    except Exception as e:
        checks.append(ReleaseCheck("package version", "warn", str(e)[:120]))

    cargo = __import__("shutil").which("cargo")
    rs_dir = root / "meris-rs"
    if cargo and rs_dir.is_dir():
        code, out = _run(["cargo", "test", "-q"], cwd=rs_dir, timeout=600)
        checks.append(
            ReleaseCheck(
                "cargo test",
                "ok" if code == 0 else "fail",
                "meris-rs green" if code == 0 else out or f"exit {code}",
            )
        )
        code2, _ = _run([sys.executable, "scripts/check_native_parity.py"], cwd=root)
        checks.append(
            ReleaseCheck(
                "native parity",
                "ok" if code2 == 0 else "warn",
                "parity ok" if code2 == 0 else "build meris-rs for full parity",
            )
        )
    else:
        checks.append(
            ReleaseCheck(
                "meris-rs",
                "warn",
                "cargo or meris-rs/ missing — optional for release",
            )
        )

    if (root / "dist").is_dir() and list((root / "dist").glob("*.whl")):
        checks.append(ReleaseCheck("dist/", "ok", "wheel present — ready for twine upload"))
    else:
        checks.append(
            ReleaseCheck(
                "dist/",
                "warn",
                "run: python -m build  (then TWINE_* + scripts/publish-pypi.ps1)",
            )
        )

    return checks


def release_ready(checks: list[ReleaseCheck]) -> bool:
    return all(c.status != "fail" for c in checks)
