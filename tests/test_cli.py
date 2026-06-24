"""CLI smoke tests — no live API required."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from meris.cli import app

runner = CliRunner()


def test_parallel_accepts_file_only(tmp_path: Path, monkeypatch) -> None:
    """--file should work without positional TASKS (dogfood bugfix)."""
    tasks = tmp_path / "tasks.txt"
    tasks.write_text("# comment\nexplain x\n", encoding="utf-8")
    ws = tmp_path / "repo"
    ws.mkdir()
    (ws / ".meris").mkdir()
    (ws / ".meris" / "settings.json").write_text("{}", encoding="utf-8")

    async def _fake_parallel(*args, **kwargs):
        return []

    monkeypatch.setattr("meris.cli.run_parallel", _fake_parallel)

    result = runner.invoke(
        app,
        ["parallel", "--file", str(tasks), "--cwd", str(ws), "--mode", "ask"],
    )
    assert result.exit_code == 0, result.output
    assert "Missing argument" not in result.output


def test_ratchet_status_empty(tmp_path: Path) -> None:
    ws = tmp_path / "repo"
    ws.mkdir()
    (ws / ".meris" / "ratchet").mkdir(parents=True)
    result = runner.invoke(app, ["ratchet", "status", "--cwd", str(ws)])
    assert result.exit_code == 0, result.output


def test_ratchet_learn_pyproject(tmp_path: Path) -> None:
    ws = tmp_path / "repo"
    ws.mkdir()
    (ws / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (ws / ".meris").mkdir()
    result = runner.invoke(app, ["ratchet", "learn", "--init", "--cwd", str(ws)])
    assert result.exit_code == 0, result.output


def test_session_list_empty(tmp_path: Path) -> None:
    ws = tmp_path / "repo"
    ws.mkdir()
    (ws / ".meris" / "sessions").mkdir(parents=True)
    result = runner.invoke(app, ["session", "list", "--cwd", str(ws)])
    assert result.exit_code == 0
    assert "no sessions" in result.output.lower()
