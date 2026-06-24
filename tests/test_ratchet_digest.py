"""Ratchet digest / insights — active habit mining."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from meris.harness.ratchet import (
    accept_insight,
    apply_proposal,
    digest_workspace,
    dismiss_insight,
    list_insights,
    load_insight,
)
from meris.harness.ratchet.digest import digest_sessions_rule_based
from meris.harness.sessions import SessionRecord, save_session


def _seed_session(workspace: Path, sid: str, task: str, user_msgs: list[str]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec = SessionRecord(
        id=sid,
        task=task,
        mode="run",
        status="completed",
        created_at=now,
        updated_at=now,
        workspace=str(workspace),
        messages=[{"role": "user", "content": t} for t in user_msgs],
    )
    save_session(workspace, rec)


def test_digest_finds_repeated_yaml_habit(workspace: Path) -> None:
    _seed_session(
        workspace,
        "aaa111",
        "config",
        ["请用 settings.yaml，local 只覆盖 ep"],
    )
    _seed_session(
        workspace,
        "bbb222",
        "routing",
        ["深合并会替换 rules，local 只写 dynamic.enabled"],
    )
    created = digest_sessions_rule_based(workspace, since_days=30, min_sessions=2)
    assert any(i.lesson == "L-insight-settings-yaml" for i in created)
    saved = digest_workspace(workspace, since_days=30, min_sessions=2)
    assert saved
    pending = list_insights(workspace, status="pending")
    assert any(p.lesson == "L-insight-settings-yaml" for p in pending)


def test_digest_dedupes_after_apply(workspace: Path) -> None:
    _seed_session(workspace, "s1", "t", ["先不要 release"])
    _seed_session(workspace, "s2", "t", ["不打包，继续优化"])
    saved = digest_workspace(workspace, since_days=30, min_sessions=2)
    assert len(saved) == 1
    target = saved[0]
    assert target.lesson == "L-insight-no-release"
    proposal = accept_insight(workspace, target.id)
    assert proposal
    apply_proposal(workspace, proposal)
    text = (workspace / ".meris" / "rules" / "user-prefs.md").read_text(encoding="utf-8")
    assert "ratchet:L-insight-no-release" in text
    second = digest_sessions_rule_based(workspace, since_days=30, min_sessions=2)
    assert not second


def test_dismiss_insight(workspace: Path) -> None:
    _seed_session(workspace, "x1", "t", ["最小 diff，不要 over-engineer"])
    _seed_session(workspace, "x2", "t", ["minimal scope 就好"])
    created = digest_workspace(workspace, since_days=30, min_sessions=2)
    ins_id = created[0].id
    assert dismiss_insight(workspace, ins_id)
    assert load_insight(workspace, ins_id) is not None
    assert load_insight(workspace, ins_id).status == "dismissed"
    again = digest_sessions_rule_based(workspace, since_days=30, min_sessions=2)
    assert not again


def test_cli_digest_dry_run(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from meris.cli import app

    (tmp_path / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (tmp_path / ".meris" / "sessions").mkdir(parents=True)
    _seed_session(tmp_path, "c1", "t", ["settings.local 只覆盖 ep"])
    _seed_session(tmp_path, "c2", "t", ["用 yaml 配置"])

    runner = CliRunner()
    result = runner.invoke(app, ["ratchet", "digest", "--dry-run", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    assert "L-insight-settings-yaml" in result.stdout or "insight" in result.stdout.lower()
