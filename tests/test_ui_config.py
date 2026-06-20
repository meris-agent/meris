"""Tests for Agent UI config (MCP / skills / meris root)."""

from meris.harness.ui_config import (
    get_effective_mcp_servers,
    is_meris_repo_root,
    list_mcp_servers_for_ui,
    pick_plan_execute_root,
    plan_payload_for_workspace,
    save_skill,
    save_ui_mcp_servers,
)


def test_ui_mcp_overrides_settings(workspace) -> None:
    h = workspace / ".meris"
    h.mkdir(parents=True, exist_ok=True)
    (h / "settings.json").write_text(
        '{"mcpServers": {"old": {"command": "echo", "args": []}}}',
        encoding="utf-8",
    )
    save_ui_mcp_servers(workspace, {"new": {"command": "cmd", "args": ["a"], "enabled": True}})
    effective = get_effective_mcp_servers(workspace)
    assert "new" in effective
    assert "old" not in effective


def test_save_skill(workspace) -> None:
    path = save_skill(workspace, "my-skill", "# Hello")
    assert path.is_file()
    assert "Hello" in path.read_text(encoding="utf-8")


def test_is_meris_repo_root(workspace) -> None:
    (workspace / ".meris").mkdir(exist_ok=True)
    assert is_meris_repo_root(workspace)


def test_pick_plan_execute_root_prefers_nested_meris(tmp_path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".meris").mkdir()
    repo = vault / "meris"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='meris'\n", encoding="utf-8")
    (repo / "meris").mkdir()
    assert pick_plan_execute_root(vault) == repo.resolve()


def test_plan_payload_for_workspace(workspace) -> None:
    plan_dir = workspace / ".meris" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "tasks.md").write_text("- [ ] one\n", encoding="utf-8")
    payload = plan_payload_for_workspace(workspace)
    assert payload is not None
    assert payload["items"] == [{"done": False, "text": "one"}]


def test_parse_mcp_json_text(workspace) -> None:
    from meris.harness.ui_config import mcp_json_to_ui_items, parse_mcp_json_text, ui_items_to_mcp_json_text

    raw = parse_mcp_json_text(
        '{"mcpServers": {"cg": {"command": "npx", "args": ["-y", "codegraph"], "enabled": false}}}'
    )
    assert "cg" in raw
    items = mcp_json_to_ui_items(raw)
    assert items[0]["name"] == "cg"
    assert items[0]["enabled"] is False
    text = ui_items_to_mcp_json_text(items)
    assert "mcpServers" in text
    assert "codegraph" in text


def test_save_rule(workspace) -> None:
    from meris.harness.ui_config import save_rule

    path = save_rule(workspace, "my-rule", "# Rule\n")
    assert path.is_file()
    assert "Rule" in path.read_text(encoding="utf-8")


def test_import_cursor_rules(workspace) -> None:
    from meris.harness.ui_config import import_cursor_rules

    cursor_rules = workspace / ".cursor" / "rules"
    cursor_rules.mkdir(parents=True)
    (cursor_rules / "test-rule.mdc").write_text("# From Cursor\n", encoding="utf-8")
    count = import_cursor_rules(workspace)
    assert count == 1
    assert (workspace / ".meris" / "rules" / "test-rule.md").is_file()


def test_list_mcp_servers_for_ui(workspace) -> None:
    save_ui_mcp_servers(
        workspace,
        {"cg": {"command": "npx", "args": ["cg"], "enabled": False, "transport": "stdio"}},
    )
    items = list_mcp_servers_for_ui(workspace)
    assert items[0]["name"] == "cg"
    assert items[0]["enabled"] is False
