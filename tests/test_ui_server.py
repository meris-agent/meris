"""Tests for meris ui server helpers (Phase H10)."""

from __future__ import annotations

import json

from meris.ui.server import _enrich_event, load_ratchet, load_sessions


def test_load_sessions_empty(tmp_path) -> None:
    assert load_sessions(tmp_path) == []


def test_load_sessions_reads_files(tmp_path) -> None:
    sess_dir = tmp_path / ".meris" / "sessions"
    sess_dir.mkdir(parents=True)
    (sess_dir / "a.json").write_text(
        json.dumps({"id": "sess1", "task": "hi", "status": "completed"}),
        encoding="utf-8",
    )
    rows = load_sessions(tmp_path)
    assert len(rows) == 1
    assert rows[0]["id"] == "sess1"


def test_load_ratchet_empty(tmp_path) -> None:
    data = load_ratchet(tmp_path)
    assert data["proposals"] == []
    assert data["insightsPending"] == 0


def test_enrich_event_adds_git_diff(tmp_path, monkeypatch) -> None:
    ev = {"kind": "file_change", "path": "foo.txt"}

    def fake_git(*_a, **_k):
        return "+added line"

    monkeypatch.setattr("meris.ui.server._git_diff", lambda _cwd, _p: "+added line")
    out = _enrich_event(tmp_path, ev)
    assert out["diff_preview"] == "+added line"
