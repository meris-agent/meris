"""Phase G1 — sandbox presets."""

from __future__ import annotations

from meris.harness.sandbox import (
    get_network_mode,
    get_os_sandbox_mode,
    get_sandbox_mode,
    get_sandbox_preset,
)
from meris.harness.settings import load_settings


def test_default_preset_workspace_write(workspace) -> None:
    settings = load_settings(workspace)
    assert get_sandbox_preset(settings) == "workspace-write"
    assert get_network_mode(settings) == "isolated"
    assert get_sandbox_mode(settings) == "warn"


def test_explicit_preset_read_only() -> None:
    settings = {"sandbox": {"preset": "read-only"}}
    assert get_sandbox_preset(settings) == "read-only"
    assert get_sandbox_mode(settings) == "strict"
    assert get_network_mode(settings) == "isolated"
    assert get_os_sandbox_mode(settings) == "auto"


def test_explicit_preset_danger() -> None:
    settings = {"sandbox": {"preset": "danger-full-access"}}
    assert get_sandbox_mode(settings) == "off"
    assert get_network_mode(settings) == "shared"
    assert get_os_sandbox_mode(settings) == "off"


def test_explicit_field_overrides_preset() -> None:
    settings = {
        "sandbox": {
            "preset": "workspace-write",
            "network": "shared",
        }
    }
    assert get_network_mode(settings) == "shared"
    assert get_sandbox_mode(settings) == "warn"
