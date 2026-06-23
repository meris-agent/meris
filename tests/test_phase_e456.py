"""Events, review, settings merge, ratchet apply."""

from __future__ import annotations

from pathlib import Path


from meris.harness.guides import build_system_prompt
from meris.harness.protocol import EventStream
from meris.harness.ratchet.apply import apply_proposal, is_allowed_target
from meris.harness.ratchet.proposal import Proposal, ProposalTarget
from meris.harness.review import build_review_task
from meris.harness.settings import load_settings


def test_event_stream_memory() -> None:
    stream = EventStream.memory()
    stream.emit("session_start", message="hi", session="s1", mode="run")
    assert len(stream.collector) == 1
    assert stream.collector[0]["kind"] == "session_start"


def test_settings_merge_rules_by_name(tmp_path: Path) -> None:
    h = tmp_path / ".meris"
    h.mkdir()
    (h / "settings.yaml").write_text(
        """
models:
  rules:
    - name: heavy-refactor
      match:
        mode: run
      profile: heavy
""",
        encoding="utf-8",
    )
    (h / "settings.local.yaml").write_text(
        """
models:
  rules:
    - name: heavy-refactor
      match:
        taskContains: [架构]
""",
        encoding="utf-8",
    )
    merged = load_settings(tmp_path)
    rules = merged["models"]["rules"]
    assert len(rules) == 1
    rule = rules[0]
    assert rule["name"] == "heavy-refactor"
    assert rule["match"]["mode"] == "run"
    assert "架构" in rule["match"]["taskContains"]


def test_review_mode_prompt(workspace: Path) -> None:
    p = build_system_prompt(workspace, mode="review")
    assert "REVIEW" in p
    assert "write_file" in p.lower()


def test_build_review_task(monkeypatch, workspace: Path) -> None:
    monkeypatch.setattr(
        "meris.harness.review.git_diff",
        lambda ws, staged=False: "+added line\n",
    )
    task = build_review_task(workspace, staged=False)
    assert "Summary" in task
    assert "added line" in task


def test_benchmark_local_review_task() -> None:
    from meris.benchmark import _run_local_task

    root = Path(__file__).resolve().parents[1]
    out, status, _ = _run_local_task(root, "review_task")
    assert status == "pass"
    assert "## Issues" in out


def test_is_allowed_force_settings() -> None:
    assert is_allowed_target(".meris/settings.yaml", force_settings=True)
    assert not is_allowed_target(".meris/settings.yaml")


def test_apply_patch_section(workspace: Path) -> None:
    agents = workspace / "AGENTS.md"
    agents.write_text("# AGENTS\n\n## Done\n", encoding="utf-8")
    p = Proposal(
        id="ratchet-patch-1",
        lesson="L-test",
        summary="patch test",
        target=ProposalTarget(
            path="AGENTS.md",
            action="patch_section",
            content="## Ratchet patch\n\n- [ ] item\n",
        ),
    )
    apply_proposal(workspace, p, force_agents=True)
    text = agents.read_text(encoding="utf-8")
    assert "Ratchet patch" in text
    assert "ratchet:L-test" in text
