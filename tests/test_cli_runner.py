"""CLI runner allowlist for Agent Window."""

from meris.ui.cli_runner import RUNNABLE_CLI, resolve_runnable_cli
from meris.ui.harness_data import list_cli_commands_for_ui


def test_resolve_runnable_doctor() -> None:
    assert resolve_runnable_cli("doctor") == ["doctor", "--no-probe"]


def test_resolve_rejects_unknown() -> None:
    assert resolve_runnable_cli("run") is None
    assert resolve_runnable_cli("") is None


def test_catalog_marks_runnable() -> None:
    data = list_cli_commands_for_ui()
    found = False
    for group in data.get("groups") or []:
        for cmd in group.get("commands") or []:
            if cmd.get("id") == "doctor":
                assert cmd.get("runnable") is True
                found = True
    assert found
    assert "doctor" in RUNNABLE_CLI
