"""Dogfood readiness checks."""

from meris.harness.dogfood import dogfood_check_failed, run_dogfood_check


def test_dogfood_check_ok_repo(tmp_path) -> None:
    (tmp_path / "AGENTS.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "PROGRESS.md").write_text("# P\n- [x] done\n", encoding="utf-8")
    h = tmp_path / ".meris"
    h.mkdir()
    (h / "settings.json").write_text("{}", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "DOGFOOD_DAILY.md").write_text("# daily\n", encoding="utf-8")
    (docs / "harness").mkdir()
    (docs / "harness" / "README.md").write_text("# h\n", encoding="utf-8")

    rows = run_dogfood_check(tmp_path)
    assert not dogfood_check_failed(rows)
    names = {r.name for r in rows}
    assert "progress-sessions" in names
    assert "harness-check" in names


def test_dogfood_warns_open_session(tmp_path) -> None:
    (tmp_path / "AGENTS.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "PROGRESS.md").write_text(
        "## Session note\n- **Status**: dod_failed\n",
        encoding="utf-8",
    )
    h = tmp_path / ".meris"
    h.mkdir()
    (h / "settings.json").write_text("{}", encoding="utf-8")
    docs = tmp_path / "docs" / "harness"
    docs.mkdir(parents=True)
    (docs / "README.md").write_text("# h\n", encoding="utf-8")
    (tmp_path / "docs" / "DOGFOOD_DAILY.md").write_text("# d\n", encoding="utf-8")

    rows = run_dogfood_check(tmp_path)
    prog = next(r for r in rows if r.name == "progress-sessions")
    assert prog.status == "warn"
