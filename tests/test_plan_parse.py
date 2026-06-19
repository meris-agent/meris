"""Tests for plan checkbox parsing (Phase I4)."""

from meris.harness.plan import parse_plan_checkboxes


def test_parse_plan_checkboxes() -> None:
    text = "- [ ] first\n- [x] done\n- [ ] third"
    items = parse_plan_checkboxes(text)
    assert len(items) == 3
    assert items[0] == {"done": False, "text": "first"}
    assert items[1] == {"done": True, "text": "done"}
