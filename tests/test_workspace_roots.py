"""Workspace multi-root persistence for meris ui."""

from __future__ import annotations

from pathlib import Path

import pytest

from meris.harness.ui_config import (
    add_workspace_root,
    collect_workspace_folders,
    load_workspace_roots,
    remove_workspace_root,
    save_workspace_roots,
)


@pytest.fixture()
def roots_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ui_dir = tmp_path / ".meris" / "ui"
    ui_dir.mkdir(parents=True)
    target = ui_dir / "workspace-roots.json"
    monkeypatch.setattr("meris.harness.ui_config._roots_file", lambda: target)
    return target


def test_save_and_load_workspace_roots(roots_file: Path, tmp_path: Path) -> None:
    a = tmp_path / "proj-a"
    b = tmp_path / "proj-b"
    a.mkdir()
    b.mkdir()
    save_workspace_roots([a, b])
    loaded = load_workspace_roots()
    assert [str(p) for p in loaded] == [str(a.resolve()), str(b.resolve())]


def test_add_and_remove_workspace_root(roots_file: Path, tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _, created_a = add_workspace_root(a)
    _, created_b = add_workspace_root(b)
    assert created_a is True
    assert created_b is True
    assert len(load_workspace_roots()) == 2
    _, created_dup = add_workspace_root(a)
    assert created_dup is False
    remove_workspace_root(a)
    assert [str(p) for p in load_workspace_roots()] == [str(b.resolve())]


def test_collect_workspace_folders_merges_roots(roots_file: Path, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    meris = vault / "meris"
    vault.mkdir()
    meris.mkdir()
    (meris / "pyproject.toml").write_text("[project]\nname='m'\n", encoding="utf-8")
    (meris / "meris").mkdir()
    other = tmp_path / "other"
    other.mkdir()

    save_workspace_roots([vault, other])
    folders = collect_workspace_folders(meris)
    paths = {f["path"] for f in folders}
    assert str(vault.resolve()) in paths
    assert str(meris.resolve()) in paths
    assert str(other.resolve()) in paths


def test_add_workspace_root_requires_directory(roots_file: Path, tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(ValueError, match="not a directory"):
        add_workspace_root(missing)


def test_reject_skill_path_as_workspace_root(roots_file: Path, tmp_path: Path) -> None:
    from meris.harness.ui_config import is_valid_workspace_root

    skill = tmp_path / ".system" / "skill-creator"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    assert is_valid_workspace_root(skill) is False
    with pytest.raises(ValueError, match="skill"):
        add_workspace_root(skill)


def test_prune_ephemeral_pytest_roots(roots_file: Path, tmp_path: Path) -> None:
    from meris.harness.ui_config import prune_workspace_roots

    real = tmp_path / "real-project"
    real.mkdir()
    stale = tmp_path / "pytest-of-user" / "pytest-1" / "test_broadcast_workspace_switc0" / "b"
    stale.mkdir(parents=True)
    save_workspace_roots([real, stale])
    kept, removed = prune_workspace_roots()
    assert removed == 1
    assert [str(p) for p in kept] == [str(real.resolve())]


def test_stale_pytest_root_detector() -> None:
    from meris.harness.ui_config import _is_stale_pytest_workspace_root

    stale = Path("C:/Users/x/AppData/Local/Temp/pytest-of-user/pytest-206/test_foo0/b")
    assert _is_stale_pytest_workspace_root(stale) is True
    ok = Path("/home/user/projects/meris")
    assert _is_stale_pytest_workspace_root(ok) is False
