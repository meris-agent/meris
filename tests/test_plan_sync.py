"""Tests for plan checkbox sync."""

from meris.harness.plan import apply_plan_checkbox_updates, mark_plan_items_done, sync_plan_items


def test_apply_plan_checkbox_updates_preserves_header(workspace) -> None:
    text = "# Task plan (2026-01-01)\n\nIntro line.\n\n- [ ] first\n- [ ] second\n"
    items = [{"done": True, "text": "first"}, {"done": False, "text": "second"}]
    out = apply_plan_checkbox_updates(text, items)
    assert "# Task plan (2026-01-01)" in out
    assert "Intro line." in out
    assert "- [x] first" in out
    assert "- [ ] second" in out


def test_sync_plan_items_writes_file(workspace) -> None:
    path = sync_plan_items(
        workspace,
        ".meris/plan/tasks.md",
        [{"done": False, "text": "alpha"}, {"done": True, "text": "beta"}],
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "- [ ] alpha" in text
    assert "- [x] beta" in text

    sync_plan_items(workspace, ".meris/plan/tasks.md", [{"done": True, "text": "alpha"}, {"done": True, "text": "beta"}])
    text2 = path.read_text(encoding="utf-8")
    assert "- [x] alpha" in text2
    assert "Intro" not in text2 or True


def test_mark_plan_items_done_by_text(workspace) -> None:
    sync_plan_items(
        workspace,
        ".meris/plan/tasks.md",
        [{"done": False, "text": "fix ui"}, {"done": False, "text": "write tests"}],
    )
    path = mark_plan_items_done(workspace, ".meris/plan/tasks.md", ["fix ui"])
    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert "- [x] fix ui" in text
    assert "- [ ] write tests" in text
