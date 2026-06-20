"""Tests for standalone folder browser API."""

from meris.ui.harness_data import browse_directories


def test_browse_home_has_entries() -> None:
    data = browse_directories("")
    assert data["entries"]
    assert any(e["isDir"] for e in data["entries"])


def test_browse_existing_dir() -> None:
    import os

    home = os.path.expanduser("~")
    data = browse_directories(home)
    assert data["canSelect"] is True
    assert data["path"]
    assert any(e.get("isParent") for e in data["entries"])
