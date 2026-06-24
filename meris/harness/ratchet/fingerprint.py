"""Harness fingerprint — version anchor for events and Self-Harness evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path

from meris.harness.paths import harness_root


def _file_sig(path: Path) -> str:
    if not path.is_file():
        return ""
    st = path.stat()
    return f"{path.name}:{st.st_size}:{int(st.st_mtime)}"


def harness_fingerprint(workspace: Path) -> str:
    """Stable short hash over AGENTS.md + rules + skills + settings."""
    ws = workspace.resolve()
    parts: list[str] = []
    agents = ws / "AGENTS.md"
    parts.append(_file_sig(agents))

    hroot = harness_root(ws)
    for pattern in ("settings.json", "settings.yaml", "settings.yml"):
        parts.append(_file_sig(hroot / pattern))

    for sub in ("rules", "skills"):
        d = hroot / sub
        if d.is_dir():
            for fp in sorted(d.glob("*.md")):
                parts.append(_file_sig(fp))

    raw = "|".join(p for p in parts if p)
    if not raw:
        return "empty"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
