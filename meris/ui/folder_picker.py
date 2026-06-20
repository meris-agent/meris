"""Native OS folder picker for standalone Agent UI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _pick_folder_windows(initial: str) -> str | None:
    """Windows FolderBrowserDialog via PowerShell STA (stays above other windows)."""
    initial_json = json.dumps(initial or "")
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = '选择项目文件夹'
$d.ShowNewFolderButton = $true
$initial = {initial_json}
if ($initial) {{ $d.SelectedPath = $initial }}
if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
    Write-Output $d.SelectedPath
}}
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 and not (proc.stdout or "").strip():
        return None
    path = (proc.stdout or "").strip()
    return path if path else None


def _pick_folder_tkinter(initial: str) -> str | None:
    script = """
import sys

def main() -> None:
    initial = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("", end="")
        return
    root = tk.Tk()
    root.withdraw()
    try:
        root.wm_attributes("-topmost", 1)
    except Exception:
        pass
    picked = filedialog.askdirectory(
        initialdir=initial if initial else None,
        title="选择项目文件夹",
        parent=root,
    )
    root.destroy()
    print(picked or "", end="")

if __name__ == "__main__":
    main()
"""
    initial_arg = initial if initial else ""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script, initial_arg],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    path = (proc.stdout or "").strip()
    return path if path else None


def pick_native_folder(initial: Path | None = None) -> str | None:
    """Open a folder picker dialog; return absolute path or None if cancelled."""
    initial_str = ""
    if initial and initial.is_dir():
        initial_str = str(initial.resolve())

    if sys.platform == "win32":
        picked = _pick_folder_windows(initial_str)
        if picked:
            resolved = Path(picked).resolve()
            return str(resolved) if resolved.is_dir() else None

    picked = _pick_folder_tkinter(initial_str)
    if not picked:
        return None
    resolved = Path(picked).resolve()
    return str(resolved) if resolved.is_dir() else None
