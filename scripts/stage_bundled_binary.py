#!/usr/bin/env python3
"""Stage meris-rs into meris/_bundled for pip wheel packaging."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path


def bundled_dir(repo: Path) -> Path:
    return repo / "meris" / "_bundled"


def bundled_name() -> str:
    return "meris-rs.exe" if os.name == "nt" else "meris-rs"


def stage_binary(repo: Path, src: Path, *, clean: bool = False) -> Path:
    src = src.resolve()
    if not src.is_file():
        raise SystemExit(f"Source binary not found: {src}")
    dest_dir = bundled_dir(repo)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        for p in dest_dir.glob("meris-rs*"):
            p.unlink(missing_ok=True)
    dest = dest_dir / bundled_name()
    shutil.copy2(src, dest)
    if os.name != "nt":
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Copy meris-rs into meris/_bundled for wheel build")
    parser.add_argument(
        "--src",
        type=Path,
        help="Path to meris-rs binary (default: meris-rs/target/release/meris-rs)",
    )
    parser.add_argument("--clean", action="store_true", help="Remove existing staged binaries first")
    args = parser.parse_args()
    default = repo / "meris-rs" / "target" / "release" / bundled_name()
    src = args.src or default
    dest = stage_binary(repo, src, clean=args.clean)
    print(f"Staged {dest} ({dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
