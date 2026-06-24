"""Platform sandbox matrix tests."""

from __future__ import annotations

from meris.harness.doctor import check_harness
from meris.harness.sandbox import describe_platform_sandbox, get_sandbox_preset
from meris.harness.settings import load_settings


def test_sandbox_preset_default() -> None:
    assert get_sandbox_preset({"sandbox": {"preset": "workspace-write"}}) == "workspace-write"
    assert get_sandbox_preset({"sandbox": {"preset": "read-only"}}) == "read-only"


def test_describe_platform_sandbox_has_preset(workspace) -> None:
    settings = load_settings(workspace)
    desc = describe_platform_sandbox(workspace, settings)
    assert desc["preset"] == get_sandbox_preset(settings)
    assert "platformGaps" in desc


def test_doctor_shows_sandbox_preset(workspace) -> None:
    results = check_harness(workspace)
    sandbox = next(r for r in results if r.name == "sandbox")
    assert "preset=" in sandbox.detail
