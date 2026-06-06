"""Phase E1/E2 — harness docs and static checks."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from meris.cli import app
from meris.harness.check import harness_check_failed, run_harness_check
from meris.harness.guides import build_system_prompt, load_guides


def test_agents_points_to_docs_harness() -> None:
    root = Path(__file__).resolve().parents[1]
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "docs/harness" in agents


def test_docs_harness_testing_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    testing = root / "docs" / "harness" / "testing.md"
    assert testing.is_file()
    assert "pytest tests/" in testing.read_text(encoding="utf-8")


def test_rules_on_demand_index(workspace: Path) -> None:
    rules = workspace / ".meris" / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / "optional.md").write_text("# Optional rule\n\nDetail only here.\n", encoding="utf-8")
    text = load_guides(workspace)
    assert "Rules (load on demand)" in text
    assert "optional.md" in text
    assert "Detail only here" not in text


def test_rules_inject_always(workspace: Path) -> None:
    rules = workspace / ".meris" / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / "critical.md").write_text(
        "---\ninject: always\n---\n\n# Critical\n\nAlways inject this.\n",
        encoding="utf-8",
    )
    text = load_guides(workspace)
    assert "Always inject this" in text


def test_system_prompt_smaller_after_e1(workspace: Path) -> None:
    """Meris repo AGENTS slim + docs/harness should keep prompt bounded."""
    root = Path(__file__).resolve().parents[1]
    if not (root / "docs" / "harness").is_dir():
        return
    prompt = build_system_prompt(root, mode="run")
    assert len(prompt) < 28_000
    assert "docs/harness" in prompt


def test_harness_check_ok(workspace: Path) -> None:
    results = run_harness_check(workspace)
    assert not harness_check_failed(results)


def test_harness_check_forge_import(workspace: Path) -> None:
    pkg = workspace / "meris"
    pkg.mkdir(exist_ok=True)
    (pkg / "bad.py").write_text("from forge import x\n", encoding="utf-8")
    results = run_harness_check(workspace)
    assert harness_check_failed(results)
    assert any(r.name == "import:forge" and not r.ok for r in results)


def test_harness_check_skips_doc_negation(workspace: Path) -> None:
    (workspace / "meris").mkdir(exist_ok=True)
    (workspace / "AGENTS.md").write_text(
        "# AGENTS\n\nRoot README is README.md (not `meris/README.md`).\n",
        encoding="utf-8",
    )
    results = run_harness_check(workspace)
    readme = [r for r in results if r.name == "paths:readme"]
    assert readme and readme[0].ok


def test_harness_check_flags_bad_plan_path(workspace: Path) -> None:
    pkg = workspace / "meris"
    pkg.mkdir(exist_ok=True)
    (pkg / "x.py").write_text("# ok\n", encoding="utf-8")
    plan = workspace / ".meris" / "plan"
    plan.mkdir(parents=True, exist_ok=True)
    (plan / "tasks.md").write_text("- [ ] Update meris/README.md\n", encoding="utf-8")
    results = run_harness_check(workspace)
    assert any(r.name == "paths:readme" and not r.ok for r in results)


def test_cli_harness_check(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["harness", "check", "--cwd", str(workspace)])
    assert result.exit_code == 0


def test_parse_dod_bash_fence(workspace: Path) -> None:
    from meris.harness.sensors import parse_dod_from_agents

    (workspace / "AGENTS.md").write_text(
        "# AGENTS\n\n## Definition of Done\n\n```bash\npytest tests/ -q\nmeris harness check\n```\n",
        encoding="utf-8",
    )
    cmds = parse_dod_from_agents(workspace)
    assert "pytest tests/ -q" in cmds
    assert "meris harness check" in cmds


def test_format_dod_failure_detail() -> None:
    from meris.harness.sensors import format_dod_failure_detail

    out = format_dod_failure_detail("import:forge: FAIL\npaths:readme: FAIL")
    assert "meris harness check" in out
    assert "paths.md" in out


def test_benchmark_local_harness_check() -> None:
    from meris.benchmark import _run_local_task

    root = Path(__file__).resolve().parents[1]
    out, status, _ = _run_local_task(root, "harness_check")
    assert status == "pass"
    assert "import:forge: ok" in out


def test_benchmark_reject() -> None:
    from meris.benchmark import _check_expectations

    ok, msg = _check_expectations("use README.md", ["README"], ["meris/README.md"])
    assert ok is True
    ok2, msg2 = _check_expectations("edit meris/README.md", ["README"], ["meris/README.md"])
    assert ok2 is False
    assert "rejected" in msg2
