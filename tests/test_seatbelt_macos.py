"""Phase G6.2 — macOS Seatbelt sandbox (Meris-native policy, not Codex copy)."""

from __future__ import annotations

import sys

import pytest

from meris.harness.sandbox import (
    build_seatbelt_policy,
    get_sandbox_preset,
)


@pytest.fixture
def require_meris_rs():
    from meris.native import find_native_binary

    if not find_native_binary():
        pytest.skip("meris-rs required for Seatbelt policy SSOT")


def test_seatbelt_policy_network_isolated(workspace, require_meris_rs) -> None:
    settings = {"sandbox": {"network": "isolated"}}
    policy, _ = build_seatbelt_policy(workspace, settings)
    assert "(deny network*)" in policy


def test_seatbelt_workspace_write_root(workspace, require_meris_rs) -> None:
    settings = {"sandbox": {"preset": "workspace-write", "network": "shared"}}
    policy, params = build_seatbelt_policy(workspace, settings)
    assert "WORKSPACE" in policy
    assert any(p.startswith("-DWORKSPACE=") for p in params)


def test_seatbelt_read_only_no_writable_root(workspace, require_meris_rs) -> None:
    settings = {"sandbox": {"preset": "read-only"}}
    policy, params = build_seatbelt_policy(workspace, settings)
    assert '(allow file-write* (subpath (param "WORKSPACE")))' not in policy
    assert get_sandbox_preset(settings) == "read-only"


def test_seatbelt_no_global_read_star(workspace, require_meris_rs) -> None:
    settings = {"sandbox": {"preset": "workspace-write"}}
    policy, _ = build_seatbelt_policy(workspace, settings)
    assert "(allow file-read*)" not in policy


def test_seatbelt_masks_env(workspace, require_meris_rs) -> None:
    (workspace / ".env").write_text("SECRET=1\n", encoding="utf-8")
    settings = {"sandbox": {"maskSecrets": True, "preset": "workspace-write"}}
    policy, params = build_seatbelt_policy(workspace, settings)
    assert "MASK_0" in policy
    assert any(p.startswith("-DMASK_0=") for p in params)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS seatbelt integration")
def test_seatbelt_runs_echo(workspace) -> None:
    from meris.harness.sandbox import find_sandbox_exec, should_use_seatbelt

    if not find_sandbox_exec():
        pytest.skip("sandbox-exec not available")
    settings = {"sandbox": {"preset": "workspace-write", "osSandbox": "auto"}}
    if not should_use_seatbelt(settings):
        pytest.skip("seatbelt not enabled")
    from meris.harness.sandbox import _run_seatbelt_sync

    code, out = _run_seatbelt_sync(workspace, "echo seatbelt_ok", 30, settings)
    assert code == 0
    assert "seatbelt_ok" in out


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS seatbelt integration")
def test_seatbelt_blocks_write_outside_workspace(workspace, tmp_path) -> None:
    from meris.harness.sandbox import find_sandbox_exec, should_use_seatbelt

    if not find_sandbox_exec():
        pytest.skip("sandbox-exec not available")
    settings = {"sandbox": {"preset": "read-only", "osSandbox": "auto"}}
    if not should_use_seatbelt(settings):
        pytest.skip("seatbelt not enabled")
    outside = tmp_path / "outside.txt"
    from meris.harness.sandbox import _run_seatbelt_sync

    code, _ = _run_seatbelt_sync(
        workspace,
        f"echo pwned > {outside}",
        30,
        settings,
    )
    assert not outside.exists() or code != 0
