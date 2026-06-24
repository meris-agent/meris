"""TUI task input submit behavior."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_tui_submit_on_enter(tmp_path: Path) -> None:
    from meris.tui.app import MerisTUI

    ws = tmp_path
    (ws / ".meris").mkdir()
    (ws / ".meris" / "settings.json").write_text("{}", encoding="utf-8")

    app = MerisTUI(ws, mode="ask", max_turns=1)
    async with app.run_test() as pilot:
        inp = app.query_one("#task-input")
        inp.focus()
        await pilot.press(*"hello")
        assert inp.value == "hello"
        await pilot.press("enter")
        log = app.query_one("#log")
        assert ">>> hello" in str(log.lines)
