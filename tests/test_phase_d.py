"""Phase D — Rust core scaffold, brand doc, IDE extension."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meris.native import build_native, compress_messages_auto, native_status


def test_brand_doc_exists() -> None:
    root = Path(__file__).resolve().parent.parent
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "Meris" in readme
    assert "meris-agent" in readme or "Harness" in readme


def test_meris_rs_manifest() -> None:
    root = Path(__file__).resolve().parent.parent
    cargo = root / "meris-rs" / "Cargo.toml"
    assert cargo.is_file()
    assert "meris-rs" in cargo.read_text(encoding="utf-8")


def test_vscode_extension_manifest() -> None:
    root = Path(__file__).resolve().parent.parent
    pkg = root / "extensions" / "vscode-meris" / "package.json"
    data = json.loads(pkg.read_text(encoding="utf-8"))
    assert data["name"] == "meris-agent-vscode"
    assert any(c["command"] == "meris.run" for c in data["contributes"]["commands"])
    assert (root / "extensions" / "vscode-meris" / "extension.js").is_file()


def test_native_status_shape() -> None:
    info = native_status()
    assert "available" in info
    assert "binary" in info
    assert "source" in info


def test_compress_messages_auto_python_fallback() -> None:
    msgs = [{"role": "user", "content": "hello"}]
    out = compress_messages_auto(msgs, max_messages=48)
    assert out == msgs


def test_build_native_without_cargo(monkeypatch) -> None:
    monkeypatch.setattr("meris.native.shutil.which", lambda _: None)
    code, out = build_native()
    assert code == 1
    assert "cargo" in out.lower()


@pytest.mark.asyncio
async def test_cli_native_status_runs() -> None:
    from typer.testing import CliRunner

    from meris.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["native", "status"])
    assert result.exit_code == 0
    assert "available" in result.stdout.lower() or "Key" in result.stdout
