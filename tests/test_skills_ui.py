"""Tests for skills catalog and UI prefs."""

from meris.harness.skills import (
    is_skill_enabled,
    list_skill_catalog,
    list_skills,
    load_skill_content,
    skill_metadata,
)
from meris.harness.ui_config import (
    import_cursor_skills,
    import_skills_from_dir,
    install_bundled_skill,
    load_skill_prefs,
    save_skill,
    set_skill_enabled,
    set_skill_import_source,
)


def test_skill_metadata_from_frontmatter() -> None:
    text = "---\nname: demo\ndescription: Do the thing\n---\n\n# Title\n\nBody.\n"
    meta = skill_metadata(text, "fallback")
    assert meta["title"] == "demo"
    assert meta["description"] == "Do the thing"


def test_list_skill_catalog_workspace_and_builtin(workspace) -> None:
    skills = workspace / ".meris" / "skills"
    skills.mkdir(parents=True)
    (skills / "demo.md").write_text(
        "---\nname: Demo\ndescription: Workspace skill\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    catalog = list_skill_catalog(workspace)
    names = {c["name"]: c for c in catalog}
    assert "demo" in names
    assert names["demo"]["source"] == "installed"
    assert names["demo"]["title"] == "Demo"
    assert names["demo"]["description"] == "Workspace skill"
    assert names["demo"]["enabled"] is True
    # bundled templates not installed in workspace still appear
    assert any(c["source"] == "builtin" for c in catalog)


def test_skill_disable_excludes_from_index(workspace) -> None:
    skills = workspace / ".meris" / "skills"
    skills.mkdir(parents=True)
    (skills / "on.md").write_text("# on\n", encoding="utf-8")
    (skills / "off.md").write_text("# off\n", encoding="utf-8")
    set_skill_enabled(workspace, "off", False)
    assert "on" in list_skills(workspace)
    assert "off" not in list_skills(workspace)
    assert not is_skill_enabled(workspace, "off")


def test_import_cursor_skills(workspace) -> None:
    cursor = workspace / ".cursor" / "skills" / "my-skill"
    cursor.mkdir(parents=True)
    (cursor / "SKILL.md").write_text("# From Cursor\n", encoding="utf-8")
    count = import_cursor_skills(workspace)
    assert count == 1
    dst = workspace / ".meris" / "skills" / "my-skill.md"
    assert dst.is_file()
    assert "From Cursor" in dst.read_text(encoding="utf-8")


def test_install_bundled_skill(workspace) -> None:
    path = install_bundled_skill(workspace, "plan-format")
    assert path is not None
    assert path.is_file()
    again = install_bundled_skill(workspace, "plan-format")
    assert again == path


def test_skill_prefs_roundtrip(workspace) -> None:
    from meris.harness.ui_config import save_skill_prefs, set_skill_import_source

    set_skill_import_source(workspace, str(workspace / "external-skills"))
    prefs = load_skill_prefs(workspace)
    assert "external-skills" in prefs["importSourcePath"]


def test_import_skills_from_custom_dir(workspace, tmp_path) -> None:
    from meris.harness.ui_config import import_skills_from_dir, set_skill_import_source

    src = tmp_path / "my-skills"
    src.mkdir()
    (src / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
    set_skill_import_source(workspace, str(src))
    count = import_skills_from_dir(workspace, src)
    assert count == 1
    assert (workspace / ".meris" / "skills" / "alpha.md").is_file()


def test_save_skill_with_name(workspace) -> None:
    save_skill(workspace, "api-tips", "# API\n")
    catalog = list_skill_catalog(workspace)
    assert any(c["name"] == "api-tips" for c in catalog)


def test_global_skill_catalog_and_load(workspace, monkeypatch, tmp_path) -> None:
    global_dir = tmp_path / "global-skills"
    global_dir.mkdir()
    (global_dir / "shared.md").write_text("# Shared global\n", encoding="utf-8")
    monkeypatch.setattr(
        "meris.harness.skills.global_skills_dir",
        lambda: global_dir,
    )
    catalog = list_skill_catalog(workspace)
    shared = next(c for c in catalog if c["name"] == "shared")
    assert shared["source"] == "global"
    assert shared["readonly"] is False
    assert "shared" in list_skills(workspace)
    assert "Shared global" in (load_skill_content(workspace, "shared") or "")


def test_save_global_skill(workspace, monkeypatch, tmp_path) -> None:
    from meris.harness.ui_config import save_global_skill

    global_dir = tmp_path / "global-skills"
    global_dir.mkdir()
    monkeypatch.setattr(
        "meris.harness.skills.global_skills_dir",
        lambda: global_dir,
    )
    path = save_global_skill("tips", "# Tips\n")
    assert path.is_file()
    catalog = list_skill_catalog(workspace)
    assert any(c["name"] == "tips" and c["source"] == "global" for c in catalog)
