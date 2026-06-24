"""Tests for meris-agent."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from meris.harness.context import compress_messages, sanitize_messages_for_api
from meris.harness.guardrails import check_blocked_path, check_tool_guardrails
from meris.harness.permissions import check_tool_allowed, load_permissions
from meris.harness.sensors import parse_dod_from_agents, run_post_edit_sensors
from meris.harness.hooks_loader import build_hook_runner
from meris.harness.settings import load_settings
from meris.tools.mcp import _safe_name
from meris.harness.guides import build_system_prompt, load_guides
from meris.tools import build_tools


def test_load_guides(workspace: Path) -> None:
    text = load_guides(workspace)
    assert "AGENTS" in text


def test_build_system_prompt_run(workspace: Path) -> None:
    p = build_system_prompt(workspace, mode="run")
    assert "Meris" in p
    assert "AGENTS" in p


def test_build_system_prompt_ask(workspace: Path) -> None:
    p = build_system_prompt(workspace, mode="ask")
    assert "ASK" in p


def test_permission_deny_rm_rf(workspace: Path) -> None:
    settings = load_permissions(workspace)
    err = check_tool_allowed("bash", {"command": "rm -rf /tmp/x"}, settings)
    assert err is not None


def test_parse_dod(workspace: Path) -> None:
    cmds = parse_dod_from_agents(workspace)
    assert any("python" in c for c in cmds)


@pytest.mark.asyncio
async def test_read_file_tool(workspace: Path) -> None:
    tools = build_tools(workspace, read_only=True)
    out = await tools.execute("read_file", {"path": "hello.py"})
    assert "hello" in out


@pytest.mark.asyncio
async def test_glob_tool(workspace: Path) -> None:
    tools = build_tools(workspace, read_only=True)
    out = await tools.execute("glob", {"pattern": "*.py"})
    assert "hello.py" in out


@pytest.mark.asyncio
async def test_sensors_pass(workspace: Path) -> None:
    from meris.harness.sensors import run_sensors

    ok, out = await run_sensors(workspace)
    assert ok is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deepseek_api_chat() -> None:
    """Live call to DeepSeek — requires LLM_API_KEY or OPENAI_API_KEY."""
    from meris.provider import OpenAICompatProvider, ProviderError

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("no API key")

    base = (
        os.getenv("MERIS_BASE_URL")
        or os.getenv("LLM_BASE_URL")
        or os.getenv("DEEPSEEK_BASE_URL")
        or "https://api.deepseek.com/v1"
    )
    model = os.getenv("MERIS_MODEL") or os.getenv("LLM_MODEL") or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"

    provider = OpenAICompatProvider(api_key=api_key, base_url=base, model=model)
    try:
        msg = await provider.chat(
            [
                {"role": "system", "content": "Reply with exactly: pong"},
                {"role": "user", "content": "ping"},
            ]
        )
    except ProviderError as e:
        if "402" in str(e) or "Insufficient Balance" in str(e):
            pytest.skip(f"DeepSeek account balance insufficient: {e}")
        if "401" in str(e):
            pytest.skip(f"API key invalid — restart terminal after updating env: {e}")
        raise
    assert msg.get("content")
    assert "pong" in msg["content"].lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deepseek_agent_ask(workspace: Path) -> None:
    from meris.loop import agent_loop
    from meris.provider import OpenAICompatProvider, ProviderError

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("no API key")

    base = os.getenv("MERIS_BASE_URL") or os.getenv("LLM_BASE_URL") or "https://api.deepseek.com/v1"
    model = os.getenv("MERIS_MODEL") or os.getenv("LLM_MODEL") or "deepseek-chat"
    provider = OpenAICompatProvider(api_key=api_key, base_url=base, model=model)

    lines: list[str] = []
    try:
        async for line in agent_loop(
            workspace,
            "What does hello.py print? Use read_file only.",
            mode="ask",
            provider=provider,
            max_turns=8,
            run_sensors_at_end=False,
        ):
            lines.append(line)
    except ProviderError as e:
        if "402" in str(e) or "Insufficient Balance" in str(e):
            pytest.skip(f"DeepSeek account balance insufficient: {e}")
        if "401" in str(e):
            pytest.skip(f"API key invalid: {e}")
        raise

    joined = "\n".join(lines)
    assert "hello" in joined.lower() or "[assistant]" in joined or "session=" in joined


def test_session_save_load(workspace: Path) -> None:
    from meris.harness.sessions import SessionRecord, load_session, save_session

    rec = SessionRecord(id="test01", task="do thing", mode="ask", messages=[{"role": "user", "content": "hi"}])
    save_session(workspace, rec)
    loaded = load_session(workspace, "test01")
    assert loaded is not None
    assert loaded.task == "do thing"
    assert len(loaded.messages) == 1


def test_skills_index_and_load(workspace: Path) -> None:
    from meris.harness.skills import list_skills, load_skill_content, skills_index

    skills = workspace / ".meris" / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "pytest.md").write_text("# pytest tips\n", encoding="utf-8")
    assert "pytest" in list_skills(workspace)
    assert "pytest" in skills_index(workspace)
    assert "pytest tips" in load_skill_content(workspace, "pytest")


def test_build_system_prompt_includes_skills(workspace: Path) -> None:
    skills = workspace / ".meris" / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "api.md").write_text("# API\n", encoding="utf-8")
    p = build_system_prompt(workspace, mode="run")
    assert "load_skill" in p
    assert "api" in p


@pytest.mark.asyncio
async def test_load_skill_tool(workspace: Path) -> None:
    skills = workspace / ".meris" / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "demo.md").write_text("skill body", encoding="utf-8")
    tools = build_tools(workspace, read_only=True)
    out = await tools.execute("load_skill", {"name": "demo"})
    assert "skill body" in out


@pytest.mark.asyncio
async def test_parallel_empty_tasks(workspace: Path) -> None:
    from meris.parallel import run_parallel

    results = await run_parallel(workspace, [], mode="ask")
    assert results == []


def test_load_settings_merges_defaults(workspace: Path) -> None:
    s = load_settings(workspace)
    assert s["context"]["maxMessages"] == 48
    assert s["context"]["maxTokens"] == 32000
    assert "blockedPaths" in s


def test_load_settings_local_json(workspace: Path) -> None:
    from meris.harness.paths import HARNESS_DIR

    h = workspace / HARNESS_DIR
    h.mkdir(parents=True, exist_ok=True)
    (h / "settings.json").write_text(
        json.dumps({"models": {"byMode": {"ask": {"provider": "openai", "model": "gpt-4o-mini"}}}}),
        encoding="utf-8",
    )
    (h / "settings.local.json").write_text(
        json.dumps({"models": {"byMode": {"run": {"provider": "volcengine", "model": "ep-local"}}}}),
        encoding="utf-8",
    )
    s = load_settings(workspace)
    assert s["models"]["byMode"]["ask"]["provider"] == "openai"
    assert s["models"]["byMode"]["run"]["model"] == "ep-local"


def test_load_settings_yaml(workspace: Path) -> None:
    from meris.harness.paths import HARNESS_DIR

    h = workspace / HARNESS_DIR
    h.mkdir(parents=True, exist_ok=True)
    (h / "settings.yaml").write_text(
        """
permissions:
  allow: [Read]
models:
  profiles:
    fast:
      provider: openai
      model: gpt-4o-mini
  byMode:
    ask:
      profile: fast
""",
        encoding="utf-8",
    )
    (h / "settings.local.yaml").write_text(
        """
models:
  dynamic:
    enabled: true
""",
        encoding="utf-8",
    )
    s = load_settings(workspace)
    assert s["permissions"]["allow"] == ["Read"]
    assert s["models"]["byMode"]["ask"]["profile"] == "fast"
    assert s["models"]["dynamic"]["enabled"] is True


def test_compress_messages_drops_old() -> None:
    msgs = [{"role": "system", "content": "sys"}]
    msgs.append({"role": "user", "content": "task"})
    for i in range(60):
        msgs.append({"role": "assistant", "content": f"a{i}"})
        msgs.append({"role": "user", "content": f"u{i}"})
    out = compress_messages(msgs, max_messages=10)
    assert len(out) <= 10
    assert out[1]["content"] == "task"
    assert any("compressed" in m.get("content", "") for m in out)


def test_sanitize_drops_orphan_tool_messages() -> None:
    bad = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "task"},
        {"role": "system", "content": "[meris] Context compressed"},
        {"role": "tool", "tool_call_id": "call_1", "content": "orphan"},
    ]
    out = sanitize_messages_for_api(bad)
    assert not any(m.get("role") == "tool" for m in out)


def test_compress_with_tool_round_stays_api_valid() -> None:
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]
    for i in range(40):
        msgs.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            }
        )
        msgs.append({"role": "tool", "tool_call_id": f"call_{i}", "content": "ok"})
        msgs.append({"role": "assistant", "content": f"step {i}"})
    out = compress_messages(msgs, max_messages=12)
    pending: set[str] = set()
    for m in out:
        role = m.get("role")
        if role == "tool":
            assert m.get("tool_call_id") in pending
            pending.discard(m.get("tool_call_id"))
        elif pending:
            pending.clear()
        if role == "assistant" and m.get("tool_calls"):
            pending = {tc["id"] for tc in m["tool_calls"]}
        elif role == "assistant":
            pending.clear()
    assert not pending


def test_guardrails_block_generated() -> None:
    err = check_tool_guardrails(
        "write_file",
        {"path": "src/generated/foo.py"},
        blocked_paths=["**/generated/**"],
    )
    assert err is not None


def test_guardrails_allow_normal_path() -> None:
    err = check_blocked_path("src/main.py", ["**/generated/**"])
    assert err is None


@pytest.mark.asyncio
async def test_post_edit_sensors_empty(workspace: Path) -> None:
    ok, out = await run_post_edit_sensors(workspace)
    assert ok is True
    assert out == ""


@pytest.mark.asyncio
async def test_git_status_tool(workspace: Path) -> None:
    import subprocess

    subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=False)
    tools = build_tools(workspace, read_only=True)
    out = await tools.execute("git_status", {})
    assert "git" not in out.lower() or "main" in out.lower() or out.startswith("??") or "(clean" in out


def test_hooks_matcher() -> None:
    from meris.harness.hooks_loader import _matches

    assert _matches("bash", "bash") is True
    assert _matches("bash", "read_file") is False
    assert _matches("write_file|edit_file", "write_file") is True


@pytest.mark.asyncio
async def test_hooks_pre_block(workspace: Path) -> None:
    settings = load_settings(workspace)
    settings["hooks"] = {
        "preToolUse": [{"matcher": "bash", "command": "exit 1"}],
    }
    runner = build_hook_runner(workspace, settings)
    result = await runner.run_pre("bash", {"command": "echo hi"})
    assert result.block is True


@pytest.mark.asyncio
async def test_hooks_pre_skip_non_match(workspace: Path) -> None:
    settings = load_settings(workspace)
    settings["hooks"] = {
        "preToolUse": [{"matcher": "bash", "command": "exit 1"}],
    }
    runner = build_hook_runner(workspace, settings)
    result = await runner.run_pre("read_file", {"path": "x"})
    assert result.block is False


def test_mcp_safe_name() -> None:
    assert _safe_name("fs", "read-file").startswith("mcp_fs_")


def test_settings_hooks_defaults(workspace: Path) -> None:
    s = load_settings(workspace)
    assert "preToolUse" in s["hooks"]
    assert "mcpServers" in s


@pytest.mark.asyncio
async def test_build_all_tools_no_mcp(workspace: Path) -> None:
    from meris.tools import build_all_tools

    reg, mgr, notes = await build_all_tools(workspace, read_only=True, settings=load_settings(workspace))
    assert mgr is None or not mgr.servers
    assert await reg.execute("read_file", {"path": "hello.py"})
