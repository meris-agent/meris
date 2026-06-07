"""Phase G3 — platform sandbox matrix and Codex preset hints."""

from __future__ import annotations

import sys

import pytest

from meris.harness.doctor import check_harness
from meris.harness.sandbox import (
    describe_platform_sandbox,
    format_codex_preset_hint,
    get_sandbox_preset,
)


def test_codex_preset_hint_default() -> None:
    assert format_codex_preset_hint("workspace-write") == "≈ Codex --sandbox workspace-write"
    assert format_codex_preset_hint("danger-full-access") == "≈ Codex --sandbox danger-full-access"


def test_codex_preset_hint_from_settings() -> None:
    settings = {"sandbox": {"preset": "read-only"}}
    assert "read-only" in format_codex_preset_hint(settings=settings)


def test_describe_platform_sandbox_has_codex(workspace) -> None:
    settings = {"sandbox": {"preset": "workspace-write"}}
    desc = describe_platform_sandbox(workspace, settings)
    assert desc["preset"] == "workspace-write"
    assert "Codex" in str(desc["codexEquivalent"])
    assert desc["policyLayer"] is True
    assert desc["status"] in ("ok", "warn")
    assert "detail" in desc


def test_doctor_shows_codex_preset(workspace) -> None:
    results = check_harness(workspace)
    sandbox = next(r for r in results if r.name == "sandbox")
    assert "preset=workspace-write" in sandbox.detail
    assert "Codex --sandbox" in sandbox.detail
    platform = next(r for r in results if r.name == "platform sandbox")
    assert platform.status in ("ok", "warn")
    assert "PLATFORM_MATRIX.md" in platform.detail


@pytest.mark.skipif(sys.platform != "linux", reason="linux bwrap path")
def test_describe_linux_when_bwrap_available(workspace) -> None:
    desc = describe_platform_sandbox(workspace, {"sandbox": {"osSandbox": "auto"}})
    assert desc["platform"] == "linux"
