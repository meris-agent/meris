"""Tests for file_change diff preview."""

from meris.harness.diff_preview import build_file_change_preview


def test_write_file_preview() -> None:
    out = build_file_change_preview("write_file", {"path": "foo.py", "content": "a\nb\n"})
    assert "+++ foo.py" in out
    assert "+a" in out
    assert "+b" in out


def test_edit_file_preview() -> None:
    out = build_file_change_preview(
        "edit_file",
        {"path": "x.md", "old_string": "old", "new_string": "new"},
    )
    assert "--- x.md" in out
    assert "-old" in out
    assert "+new" in out


def test_unknown_tool_empty() -> None:
    assert build_file_change_preview("read_file", {"path": "a"}) == ""
