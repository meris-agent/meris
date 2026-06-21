"""F3-M2 — pip bundled meris-rs binary."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path


from meris.native import _binary_source, _bundled_dir, find_native_binary


def test_bundled_dir_exists() -> None:
    assert _bundled_dir().is_dir()


def test_stage_bundled_binary_script(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    fake = tmp_path / "meris-rs"
    fake.write_bytes(b"fake-binary")
    if os.name != "nt":
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/stage_bundled_binary.py",
            "--src",
            str(fake),
            "--clean",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    staged = _bundled_dir() / ("meris-rs.exe" if os.name == "nt" else "meris-rs")
    assert staged.is_file()
    assert staged.read_bytes() == b"fake-binary"
    try:
        assert _binary_source(staged) == "bundled"
        assert find_native_binary() == staged
    finally:
        staged.unlink(missing_ok=True)


def test_binary_source_dev_vs_path() -> None:
    repo = Path(__file__).resolve().parents[1]
    dev = repo / "meris-rs" / "target" / "release" / "meris-rs"
    assert _binary_source(dev) in ("dev", "path")
