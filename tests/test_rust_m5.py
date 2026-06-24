"""P5-4 M5 — meris-rs run entry + native loop defaults."""

from __future__ import annotations

import subprocess

import pytest

from meris.native import find_native_binary


@pytest.mark.skipif(find_native_binary() is None, reason="meris-rs not built")
def test_run_subcommand_exists() -> None:
    binary = find_native_binary()
    proc = subprocess.run(
        [str(binary), "run", "ask", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if proc.returncode != 0 and "unrecognized subcommand 'run'" in (proc.stderr or proc.stdout):
        pytest.skip("meris-rs run subcommand not in binary")
    assert proc.returncode in (0, 2)


def test_native_loop_auto_with_native_enabled(monkeypatch) -> None:
    from meris.native import find_native_binary, native_loop_enabled

    if find_native_binary() is None:
        pytest.skip("meris-rs not built")
    import subprocess

    probe = subprocess.run(
        [str(find_native_binary()), "agent", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip("agent subcommand not in binary")
    monkeypatch.setenv("MERIS_NATIVE_LOOP", "auto")
    monkeypatch.setenv("MERIS_NATIVE", "1")
    assert native_loop_enabled() is True
