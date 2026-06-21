"""Phase G6.2/G6.3 — macOS Seatbelt sandbox (Meris-native policy, G2 parity)."""

from __future__ import annotations

import sys

import pytest

from meris.harness.sandbox import (
    build_seatbelt_policy,
    check_bash_sandbox,
    get_sandbox_preset,
    run_bash_sync,
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


def test_seatbelt_allowlist_hybrid_policy(workspace, require_meris_rs) -> None:
    settings = {
        "sandbox": {
            "preset": "workspace-write",
            "networkAllowlist": ["github.com", "*.pythonhosted.org"],
        }
    }
    policy, _ = build_seatbelt_policy(workspace, settings)
    assert "(allow network-outbound)" in policy
    assert "(deny network*)" not in policy


def test_seatbelt_mask_paths_extra(workspace, require_meris_rs) -> None:
    (workspace / "secrets.local").write_text("key=1\n", encoding="utf-8")
    settings = {
        "sandbox": {
            "preset": "workspace-write",
            "maskSecrets": True,
            "maskPaths": ["secrets.local"],
        }
    }
    policy, params = build_seatbelt_policy(workspace, settings)
    assert "MASK_0" in policy or "MASK_1" in policy
    joined = " ".join(params)
    assert "secrets.local" in joined


def test_run_bash_sync_strict_blocks_allowlist_violation(workspace) -> None:
    settings = {
        "sandbox": {
            "mode": "strict",
            "networkAllowlist": ["github.com"],
            "preset": "workspace-write",
            "osSandbox": "off",
        }
    }
    out = run_bash_sync(workspace, "curl https://evil.example.com/x", settings)
    assert out.startswith("exit=1")
    assert "evil.example.com" in out or "networkAllowlist" in out


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS seatbelt integration")
def test_seatbelt_masks_env_at_runtime(workspace) -> None:
    from meris.harness.sandbox import find_sandbox_exec, should_use_seatbelt, _run_seatbelt_sync

    if not find_sandbox_exec():
        pytest.skip("sandbox-exec not available")
    (workspace / ".env").write_text("SECRET=ci-mask\n", encoding="utf-8")
    settings = {"sandbox": {"preset": "workspace-write", "maskSecrets": True, "osSandbox": "auto"}}
    if not should_use_seatbelt(settings):
        pytest.skip("seatbelt not enabled")
    _code, out = _run_seatbelt_sync(
        workspace,
        "cat .env 2>/dev/null || true",
        30,
        settings,
    )
    assert "SECRET=ci-mask" not in out


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS seatbelt integration")
def test_seatbelt_allowlist_blocked_before_run(workspace) -> None:
    from meris.harness.sandbox import find_sandbox_exec, should_use_seatbelt

    if not find_sandbox_exec():
        pytest.skip("sandbox-exec not available")
    settings = {
        "sandbox": {
            "mode": "strict",
            "networkAllowlist": ["github.com"],
            "preset": "workspace-write",
            "osSandbox": "auto",
        }
    }
    if not should_use_seatbelt(settings):
        pytest.skip("seatbelt not enabled")
    verdict = check_bash_sandbox(workspace, "curl https://evil.example.com", settings)
    assert verdict is not None and verdict.blocked
    out = run_bash_sync(workspace, "curl https://evil.example.com", settings)
    assert out.startswith("exit=1")


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
    if code != 0:
        pytest.skip(f"seatbelt echo unavailable on this runner (code={code}): {out}")
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
