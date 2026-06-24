"""Workspace switch keeps server.workspace in sync with runtime."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from meris.ui import server as ui_server


@pytest.fixture()
def isolated_roots_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ui_dir = tmp_path / ".meris" / "ui"
    ui_dir.mkdir(parents=True)
    target = ui_dir / "workspace-roots.json"
    monkeypatch.setattr("meris.harness.ui_config._roots_file", lambda: target)
    return target


def test_broadcast_workspace_switch_updates_httpd_workspace(
    tmp_path: Path, isolated_roots_file: Path
) -> None:
    from meris.harness.ui_config import load_workspace_roots

    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    rt = ui_server.UiRuntime(a)
    httpd = MagicMock()
    httpd.workspace = str(a)

    ui_server._broadcast_workspace_switch(rt, b, httpd)

    assert httpd.workspace == str(b.resolve())
    assert ui_server._RUNTIME is not None
    assert ui_server._RUNTIME.cwd == b.resolve()
    assert str(b.resolve()) in [str(p) for p in load_workspace_roots()]
    assert str(a.resolve()) not in [str(p) for p in load_workspace_roots()]
