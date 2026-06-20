"""Task scope persistence and normalization."""

from __future__ import annotations

from pathlib import Path

import pytest

from meris.harness.ui_config import (
    load_task_scope_paths,
    normalize_task_scope,
    save_task_scope,
    set_task_scope,
    task_scope_payload,
)


@pytest.fixture()
def scope_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ui_dir = tmp_path / ".meris" / "ui"
    ui_dir.mkdir(parents=True)
    target = ui_dir / "task-scope.json"
    monkeypatch.setattr("meris.harness.ui_config._task_scope_file", lambda: target)
    return target


def test_empty_scope_defaults_to_cwd(scope_file: Path, tmp_path: Path) -> None:
    cwd = tmp_path / "main"
    other = tmp_path / "other"
    cwd.mkdir()
    other.mkdir()
    assert normalize_task_scope([], available=[cwd, other], cwd=cwd) == [cwd.resolve()]


def test_save_load_and_normalize(scope_file: Path, tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    c = tmp_path / "c"
    a.mkdir()
    b.mkdir()
    c.mkdir()
    save_task_scope([a, b])
    assert [str(p) for p in load_task_scope_paths()] == [str(a.resolve()), str(b.resolve())]
    # stale path dropped
    normalized = normalize_task_scope([a, c], available=[a, b], cwd=a)
    assert normalized == [a.resolve()]
    # empty after filter -> cwd
    normalized2 = normalize_task_scope([c], available=[a, b], cwd=b)
    assert normalized2 == [b.resolve()]


def test_set_task_scope_persists(scope_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ui_dir = tmp_path / ".meris" / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    roots = ui_dir / "workspace-roots.json"
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    roots.write_text(
        '{"roots": ["' + str(a.resolve()).replace("\\", "\\\\") + '", "'
        + str(b.resolve()).replace("\\", "\\\\")
        + '"]}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("meris.harness.ui_config._roots_file", lambda: roots)

    selected = set_task_scope([b], cwd=a)
    assert selected == [b.resolve()]
    payload = task_scope_payload(a)
    paths = {item["path"] for item in payload["taskScope"]}
    assert str(a.resolve()) in paths
    assert str(b.resolve()) in paths
    selected_items = [i for i in payload["taskScope"] if i["selected"]]
    assert len(selected_items) == 1
    assert selected_items[0]["path"] == str(b.resolve())
