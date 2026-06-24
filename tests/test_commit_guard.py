"""Tests for meris.harness.commit_guard."""

from __future__ import annotations

from pathlib import Path

from meris.harness.commit_guard import (
    check_file_content,
    check_paths,
    load_commit_guard_rules,
    run_commit_guard,
)


def test_forbidden_env_not_example() -> None:
    assert check_paths([".env"])
    assert check_paths([".env.local"])
    assert not check_paths([".env.example"])


def test_forbidden_meris_runtime_paths() -> None:
    hits = check_paths([".meris/sessions/foo.json", ".meris/settings.local.yaml"])
    assert len(hits) == 2


def test_detect_sk_key_in_content(tmp_path: Path) -> None:
    fp = tmp_path / "leak.py"
    token = "sk-" + "1234567890abcdefghij"
    fp.write_text(f'API_KEY = "{token}"\n', encoding="utf-8")
    findings = check_file_content(tmp_path, "leak.py")
    assert any(f.rule == "secret:openai_key" for f in findings)


def test_placeholder_line_skipped(tmp_path: Path) -> None:
    fp = tmp_path / "doc.md"
    fp.write_text("Set TWINE_PASSWORD to pypi-... in your shell (do not commit).\n", encoding="utf-8")
    assert not check_file_content(tmp_path, "doc.md")


def test_run_commit_guard_paths_only(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    findings = run_commit_guard(tmp_path, [".env"], scan_content=False)
    assert findings and findings[0].rule == "forbidden_path"


def test_extra_patterns_from_meris_config(tmp_path: Path) -> None:
    meris = tmp_path / ".meris"
    meris.mkdir()
    (meris / "commit-guard.yaml").write_text(
        "extra_patterns:\n"
        "  - regex: 'PRIVATE_ORG_MARKER_123'\n"
        "    rule: org:test\n"
        "    label: test marker\n",
        encoding="utf-8",
    )
    fp = tmp_path / "note.md"
    fp.write_text("remote = PRIVATE_ORG_MARKER_123\n", encoding="utf-8")
    rules = load_commit_guard_rules(tmp_path)
    findings = check_file_content(tmp_path, "note.md", rules=rules)
    assert any(f.rule == "org:test" for f in findings)
