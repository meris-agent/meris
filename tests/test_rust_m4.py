"""P5-4 M4 — plan save parity tests."""

from __future__ import annotations

import subprocess

import pytest

from meris.native import find_native_binary


@pytest.mark.skipif(find_native_binary() is None, reason="meris-rs not built")
def test_agent_has_event_stream_flag() -> None:
    binary = find_native_binary()
    proc = subprocess.run(
        [str(binary), "agent", "run", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip("agent run not in binary")
    assert "event-stream" in proc.stdout
