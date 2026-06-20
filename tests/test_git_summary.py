"""Git summary helpers for Agent Window."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from meris.harness.git_summary import (
    git_commit,
    git_stage_all,
    git_summary,
    git_summary_for_roots,
    is_git_repo,
    suggest_commit_message,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "init")
    return root


def test_not_a_repo(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert not is_git_repo(plain)
    summary = git_summary(plain)
    assert summary["isRepo"] is False
    assert summary["dirty"] is False


def test_dirty_and_stage_commit(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("hello world\n", encoding="utf-8")
    (git_repo / "new.txt").write_text("x\n", encoding="utf-8")
    summary = git_summary(git_repo)
    assert summary["isRepo"] is True
    assert summary["dirty"] is True
    assert summary["unstagedCount"] >= 1

    staged = git_stage_all(git_repo)
    assert staged["ok"] is True
    after_stage = staged["summary"]
    assert after_stage["stagedCount"] >= 1

    msg = suggest_commit_message(git_repo)
    assert msg
    committed = git_commit(git_repo, msg)
    assert committed["ok"] is True
    clean = committed["summary"]
    assert clean["dirty"] is False


def test_summary_for_roots_dedupes(git_repo: Path) -> None:
    (git_repo / "x.py").write_text("1\n", encoding="utf-8")
    rows = git_summary_for_roots([git_repo, git_repo])
    assert len(rows) == 1
    assert rows[0]["dirty"] is True
