"""Composer image context (Phase J7)."""

import base64

import pytest

from meris.ui.harness_data import _MAX_CONTEXT_IMAGE_BYTES, save_context_image_for_ui

_PNG_1X1 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_save_context_image_for_ui(tmp_path) -> None:
    item = save_context_image_for_ui(tmp_path, data_url=_PNG_1X1, filename="shot.png")
    assert item["kind"] == "image"
    assert item["path"].startswith(".meris/context/images/")
    assert item["path"].endswith("shot.png")
    saved = tmp_path / item["path"]
    assert saved.is_file()
    assert saved.stat().st_size > 0


def test_save_context_image_rejects_invalid(tmp_path) -> None:
    with pytest.raises(ValueError, match="invalid"):
        save_context_image_for_ui(tmp_path, data_url="not-an-image", filename="x.png")


def test_save_context_image_rejects_oversize(tmp_path) -> None:
    huge_b64 = base64.b64encode(b"x" * (_MAX_CONTEXT_IMAGE_BYTES + 1)).decode()
    data_url = "data:image/png;base64," + huge_b64
    with pytest.raises(ValueError, match="too large"):
        save_context_image_for_ui(tmp_path, data_url=data_url, filename="big.png")
