"""CLI command catalog for Agent Window."""

from meris.ui.harness_data import list_cli_commands_for_ui


def test_list_cli_commands_for_ui() -> None:
    data = list_cli_commands_for_ui()
    groups = data.get("groups") or []
    assert len(groups) >= 5
    core = next((g for g in groups if g.get("id") == "core"), None)
    assert core is not None
    ids = {c["id"] for c in core.get("commands") or []}
    assert "run" in ids
    assert "ask" in ids
    assert "plan" in ids
