"""Tests for harness UI data helpers."""

from meris.harness.ui_config import mcp_config_source
from meris.ui.harness_data import list_dir_entries, list_mcp_for_ui, list_skills_for_ui, read_skill_for_ui


def test_list_dir_entries(workspace) -> None:
    (workspace / "src").mkdir()
    (workspace / "src" / "main.py").write_text("x", encoding="utf-8")
    entries = list_dir_entries(workspace, "")
    names = {e["name"] for e in entries}
    assert "src" in names
    sub = list_dir_entries(workspace, "src")
    assert any(e["name"] == "main.py" and not e["isDir"] for e in sub)


def test_list_and_read_skills(workspace) -> None:
    skills = workspace / ".meris" / "skills"
    skills.mkdir(parents=True)
    (skills / "demo.md").write_text(
        "---\nname: Demo\ndescription: A demo skill\n---\n\n# Demo skill\n",
        encoding="utf-8",
    )
    listed = list_skills_for_ui(workspace)
    demo = next(x for x in listed if x["name"] == "demo")
    assert demo["title"] == "Demo"
    assert demo["description"] == "A demo skill"
    assert demo["source"] == "installed"
    item = read_skill_for_ui(workspace, "demo")
    assert item is not None
    assert "Demo skill" in item["content"]


def test_mcp_config_source_ui_vs_settings(workspace) -> None:
    assert mcp_config_source(workspace) == "settings"
    ui_dir = workspace / ".meris" / "ui"
    ui_dir.mkdir(parents=True)
    (ui_dir / "mcp-servers.json").write_text('{"mcpServers": {}}', encoding="utf-8")
    assert mcp_config_source(workspace) == "ui"
    info = list_mcp_for_ui(workspace, probe=False)
    assert info["source"] == "ui"


def test_migrate_mcp_to_ui(workspace) -> None:
    from meris.harness.ui_config import migrate_mcp_to_ui, mcp_config_source

    settings = workspace / ".meris" / "settings.yaml"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(
        'mcpServers:\n  demo:\n    command: echo\n    args: ["hi"]\n',
        encoding="utf-8",
    )
    assert mcp_config_source(workspace) == "settings"
    assert migrate_mcp_to_ui(workspace) is True
    assert mcp_config_source(workspace) == "ui"
    assert migrate_mcp_to_ui(workspace) is False
