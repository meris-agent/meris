"""Agent loop — async kernel (Claude Code / Nanobot shape)."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import AsyncIterator, Union

from meris.harness.context import estimate_messages_tokens, sanitize_messages_for_api
from meris.native import compress_messages_auto
from meris.harness.guardrails import check_tool_guardrails
from meris.harness.guides import build_system_prompt
from meris.harness.hooks import HookRunner
from meris.harness.hooks_loader import build_hook_runner
from meris.harness.memory import load_progress_for_prompt, update_progress_task
from meris.harness.permissions import check_tool_allowed
from meris.harness.protocol import EventStream
from meris.harness.sensors import run_post_edit_sensors, run_sensors
from meris.harness.sessions import SessionRecord, load_session, new_session_id, save_session
from meris.harness.settings import load_settings
from meris.harness.spec import load_spec_context
from meris.provider import Provider
from meris.provider.factory import get_provider_for_task, get_provider_from_overrides
from meris.provider.dynamic_router import pick_model_for_turn
from meris.state import AgentState
from meris.tools import build_all_tools

ApproveFn = Callable[[str, dict], Union[bool, Awaitable[bool]]]
EmitFn = Callable[[str], None]


async def _provider_chat_with_events(
    provider,
    messages: list[dict],
    tools: list[dict] | None,
    *,
    event_stream: EventStream | None,
    session: str,
    turn: int,
) -> dict:
    """Call provider; emit live token stream when supported."""
    if event_stream and hasattr(provider, "chat_stream"):
        msg: dict = {"content": ""}
        chunk_idx = 0
        reasoning_idx = 0
        async for item in provider.chat_stream(messages, tools=tools):
            if item.get("type") == "token":
                event_stream.emit(
                    "token",
                    message=item["delta"],
                    session=session,
                    turn=turn,
                    chunk=chunk_idx,
                )
                chunk_idx += 1
            elif item.get("type") == "reasoning":
                event_stream.emit(
                    "reasoning",
                    message=item["delta"],
                    session=session,
                    turn=turn,
                    chunk=item.get("chunk", reasoning_idx),
                )
                reasoning_idx += 1
            elif item.get("type") == "done":
                return item["message"]
        return msg

    msg = await provider.chat(messages, tools=tools)
    content = msg.get("content") or ""
    if event_stream and content:
        chunk_size = 320
        for i in range(0, len(content), chunk_size):
            event_stream.emit(
                "token",
                message=content[i : i + chunk_size],
                session=session,
                turn=turn,
                chunk=i // chunk_size,
            )
    return msg


def _emit_thinking(
    event_stream: EventStream | None,
    message: str,
    *,
    session: str,
    turn: int,
) -> None:
    if event_stream and message:
        event_stream.emit("thinking", message=message[:500], session=session, turn=turn)


async def _maybe_approve(approve_fn: ApproveFn | None, name: str, args: dict) -> bool:
    if not approve_fn:
        return False
    result = approve_fn(name, args)
    if inspect.isawaitable(result):
        return await result
    return bool(result)


def _needs_approval(tools, name: str) -> bool:
    tool = tools.get(name)
    return tool is not None and not tool.read_only


def _persist_session(
    workspace: Path,
    record: SessionRecord,
    state: AgentState,
    status: str,
) -> None:
    record.messages = state.messages
    record.turn = state.turn
    record.status = status
    save_session(workspace, record)


async def agent_loop(
    workspace: Path,
    task: str,
    *,
    mode: str = "run",
    provider: Provider | None = None,
    max_turns: int = 30,
    run_sensors_at_end: bool = True,
    require_approval: bool = False,
    approve_fn: ApproveFn | None = None,
    session_id: str | None = None,
    resume: bool = False,
    cancel: asyncio.Event | None = None,
    plan_output: str | Path | None = "__default__",
    event_stream: EventStream | None = None,
    event_stream_path: str | Path | None = None,
) -> AsyncIterator[str]:
    """Yield human-readable progress lines."""
    ws = workspace.resolve()

    from meris.native import native_loop_enabled, stream_native_agent_loop

    if (
        native_loop_enabled()
        and mode in ("ask", "plan", "review", "run")
        and provider is None
    ):
        async for line in stream_native_agent_loop(
            ws,
            task,
            mode=mode,
            max_turns=max_turns,
            session_id=session_id,
            resume=resume,
            require_approval=require_approval,
            run_sensors_at_end=run_sensors_at_end and mode == "run",
            approve_fn=approve_fn,
            event_stream_path=event_stream_path,
            save_plan=mode == "plan" and plan_output is not None,
            plan_output=None if plan_output is None else str(plan_output),
        ):
            yield line
        return

    settings = load_settings(ws)
    explicit_provider = provider is not None
    if explicit_provider:
        route_note = ""
    else:
        provider, route_note = get_provider_for_task(ws, mode, task, provider=None)

    models_cfg = settings.get("models") if isinstance(settings.get("models"), dict) else {}
    turn_overrides: dict[str, str] | None = None

    record: SessionRecord
    resumed = False
    state: AgentState

    if session_id and resume:
        loaded = load_session(ws, session_id)
        if loaded:
            record = loaded
            state = AgentState.from_session(record.messages, record.turn, record.max_turns)
            task = record.task
            mode = record.mode
            max_turns = record.max_turns
            resumed = True
        else:
            sid = session_id
            state = AgentState(max_turns=max_turns)
            record = SessionRecord(
                id=sid, task=task, mode=mode, max_turns=max_turns, workspace=str(ws)
            )
    else:
        sid = session_id or new_session_id()
        state = AgentState(max_turns=max_turns)
        record = SessionRecord(id=sid, task=task, mode=mode, max_turns=max_turns, workspace=str(ws))

    read_only = mode in ("ask", "plan", "review")
    tools, mcp_mgr, mcp_notes = await build_all_tools(ws, read_only=read_only, settings=settings)
    hooks = build_hook_runner(ws, settings)
    blocked_paths = settings.get("blockedPaths", [])
    max_messages = int(settings.get("context", {}).get("maxMessages", 48))
    max_tokens_raw = settings.get("context", {}).get("maxTokens")
    max_tokens = int(max_tokens_raw) if max_tokens_raw else None
    max_tool_tokens = int(settings.get("context", {}).get("maxToolTokens", 2000))
    post_edit_cmds = settings.get("sensors", {}).get("postEdit") or []

    if resumed:
        yield f"[meris] resumed session={session_id} turn={state.turn}"
    elif session_id and resume:
        yield f"[meris] session {session_id} not found, starting fresh"

    status = "completed"
    dod_sensor_out = ""
    lines: list[str] = []

    def emit(line: str) -> None:
        lines.append(line)

    def out(line: str, kind: str = "status", **kw: object) -> str:
        if event_stream:
            event_stream.emit(
                kind,
                message=line,
                session=record.id,
                mode=mode,
                **{k: v for k, v in kw.items() if v is not None},
            )
        return line

    if not resumed and not record.messages:
        system = build_system_prompt(ws, mode=mode)
        progress = load_progress_for_prompt(ws)
        spec_ctx = load_spec_context(ws)
        if progress:
            system += f"\n\n# Progress (read first)\n\n{progress}"
        if spec_ctx:
            system += f"\n\n# Spec\n\n{spec_ctx}"
        state.append({"role": "system", "content": system})
        state.append({"role": "user", "content": task})

    route_suffix = f" {route_note}" if route_note else ""
    yield out(
        f"[meris] workspace={ws} mode={mode} model={getattr(provider, 'model', '?')}"
        f"{route_suffix} session={record.id}",
        "session_start",
        model=getattr(provider, "model", "?"),
    )
    for note in mcp_notes:
        yield f"[meris] {note}"
    if require_approval:
        yield "[meris] approve mode ON — mutating tools need confirmation"

    try:
        while not state.done:
            if cancel and cancel.is_set():
                status = "cancelled"
                yield "[meris] cancelled — session saved"
                break

            state.next_turn()
            compressed = compress_messages_auto(
                state.messages,
                max_messages=max_messages,
                max_tokens=max_tokens,
                max_tool_tokens=max_tool_tokens,
            )
            compressed = sanitize_messages_for_api(compressed)
            before_t = estimate_messages_tokens(state.messages)
            after_t = estimate_messages_tokens(compressed)
            if len(compressed) < len(state.messages):
                note = f"context compressed {len(state.messages)} → {len(compressed)} messages"
                _emit_thinking(event_stream, note, session=record.id, turn=state.turn)
                yield f"[meris] {note}"
            elif before_t > after_t:
                note = f"token budget: {before_t} → {after_t} tokens (limit {max_tokens})"
                _emit_thinking(event_stream, note, session=record.id, turn=state.turn)
                yield f"[meris] {note}"

            if not explicit_provider and isinstance(models_cfg.get("dynamic"), dict) and models_cfg["dynamic"].get("enabled"):
                overrides, turn_note, reason = await pick_model_for_turn(
                    ws,
                    mode=mode,
                    task=task,
                    turn=state.turn,
                    messages=state.messages,
                    models_cfg=models_cfg,
                    last_overrides=turn_overrides,
                )
                if overrides:
                    prev_model = getattr(provider, "model", None)
                    if overrides != turn_overrides:
                        provider = get_provider_from_overrides(overrides)
                        turn_overrides = dict(overrides)
                        if prev_model != getattr(provider, "model", None) or turn_note.startswith("dynamic:"):
                            extra = f" ({reason})" if reason and reason != "cached" else ""
                            route_line = (
                                f"model route={turn_note} "
                                f"provider={overrides.get('provider')} model={overrides.get('model')}{extra}"
                            )
                            _emit_thinking(event_stream, route_line, session=record.id, turn=state.turn)
                            yield f"[meris] {route_line}"

            msg = await _provider_chat_with_events(
                provider,
                compressed,
                tools.schemas(),
                event_stream=event_stream,
                session=record.id,
                turn=state.turn,
            )

            if msg.get("content"):
                content = msg["content"]
                yield f"\n[assistant]\n{content}"

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                state.append({"role": "assistant", "content": msg.get("content") or ""})
                _persist_session(ws, record, state, "completed")
                break

            state.append(
                {
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )

            for tc in tool_calls:
                if cancel and cancel.is_set():
                    status = "cancelled"
                    yield "[meris] cancelled mid-tool — session saved"
                    break

                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn["arguments"])
                except json.JSONDecodeError:
                    args = {}

                denied = check_tool_allowed(name, args, settings, workspace=ws)
                if denied:
                    result = denied
                    yield f"\n[tool] {name} BLOCKED: {denied}"
                    from meris.harness.ratchet.events import record_event

                    record_event(
                        ws,
                        "permission_denied",
                        session=record.id,
                        task=task[:200],
                        detail=denied[:500],
                        tool=name,
                        tags=["permissions", name],
                    )
                else:
                    guard = check_tool_guardrails(name, args, blocked_paths=blocked_paths)
                    if guard:
                        result = guard
                        yield f"\n[tool] {name} GUARDRAIL: {guard}"
                        from meris.harness.ratchet.events import record_event

                        record_event(
                            ws,
                            "permission_denied",
                            session=record.id,
                            task=task[:200],
                            detail=guard[:500],
                            tool=name,
                            tags=["guardrail", name],
                        )
                    elif require_approval and _needs_approval(tools, name):
                        approved = await _maybe_approve(approve_fn, name, args)
                        if not approved:
                            result = "User denied tool execution"
                            status = "denied"
                            yield f"\n[tool] {name} DENIED by user"
                            from meris.harness.ratchet.events import args_summary, record_event

                            record_event(
                                ws,
                                "approve_denied",
                                session=record.id,
                                task=task[:200],
                                detail="user denied",
                                tool=name,
                                args_summary_text=args_summary(args),
                                tags=["approve", name],
                            )
                        else:
                            if event_stream:
                                event_stream.emit(
                                    "tool_start",
                                    tool=name,
                                    args=args,
                                    session=record.id,
                                    turn=state.turn,
                                )
                            result = await _run_tool(
                                hooks, tools, name, args, ws, post_edit_cmds, settings, emit
                            )
                            for line in lines:
                                yield line
                            lines.clear()
                    else:
                        if event_stream:
                            event_stream.emit(
                                "tool_start",
                                tool=name,
                                args=args,
                                session=record.id,
                                turn=state.turn,
                            )
                        result = await _run_tool(
                            hooks, tools, name, args, ws, post_edit_cmds, settings, emit
                        )
                        for line in lines:
                            yield line
                        lines.clear()

                if event_stream:
                    event_stream.emit(
                        "tool_end",
                        tool=name,
                        session=record.id,
                        preview=(result or "")[:2000],
                    )
                if event_stream and name in ("write_file", "edit_file"):
                    rel = str(args.get("path", ""))
                    if rel:
                        from meris.harness.diff_preview import build_file_change_preview

                        event_stream.emit(
                            "file_change",
                            tool=name,
                            path=rel,
                            session=record.id,
                            turn=state.turn,
                            diff_preview=build_file_change_preview(name, args),
                        )

                state.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

            _persist_session(ws, record, state, "running")

            if cancel and cancel.is_set():
                status = "cancelled"
                break

        if status != "cancelled" and run_sensors_at_end and mode == "run":
            ok, out = await run_sensors(ws)
            dod_sensor_out = out
            if not ok:
                status = "dod_failed"
            if event_stream:
                event_stream.emit("sensor", message=out[:500], ok=ok, session=record.id)
            yield f"\n[sensor] DoD {'PASS' if ok else 'FAIL'}\n{out[:2000]}"

    except asyncio.CancelledError:
        status = "cancelled"
        _persist_session(ws, record, state, status)
        yield "[meris] interrupted — session saved"
        raise
    except Exception:
        status = "error"
        raise
    finally:
        if mcp_mgr:
            await mcp_mgr.close()
        _persist_session(ws, record, state, status)
        if mode == "run" and status != "running":
            update_progress_task(ws, task[:200], status)
        if status in ("dod_failed", "error"):
            from meris.harness.check import is_harness_check_failure
            from meris.harness.ratchet import record_event

            kind = status
            detail = dod_sensor_out[:800] if dod_sensor_out else status
            if status == "dod_failed" and is_harness_check_failure(dod_sensor_out):
                kind = "harness_check_fail"
            record_event(
                ws,
                kind,
                session=record.id,
                task=task[:200],
                detail=detail,
                tags=["loop", mode, "dod"],
            )

    if mode == "plan" and plan_output is not None and status == "completed":
        from meris.harness.plan import extract_last_assistant_text, save_plan

        text = extract_last_assistant_text(state.messages)
        if text:
            out = None if plan_output == "__default__" else plan_output
            path = save_plan(ws, text, out)
            yield f"[meris] plan saved: {path}"

    if status == "dod_failed":
        from meris.harness.ratchet import list_proposals

        pending = list_proposals(ws, status="pending")
        if pending:
            yield f"[ratchet] {len(pending)} pending proposal(s) — meris ratchet review"
        else:
            yield "[ratchet] meris ratchet scan — capture harness improvements"

    if event_stream:
        event_stream.emit("done", status=status, session=record.id, mode=mode)
    yield "\n[meris] done."


async def _run_tool(
    hooks: HookRunner,
    tools,
    name: str,
    args: dict,
    workspace: Path,
    post_edit_cmds: list[str],
    settings: dict,
    emit: EmitFn,
) -> str:
    pre = await hooks.run_pre(name, args)
    if pre.block:
        emit(f"\n[tool] {name} HOOK BLOCK: {pre.message}")
        return pre.message

    if name == "bash":
        from meris.harness.sandbox import check_bash_sandbox

        verdict = check_bash_sandbox(workspace, args.get("command", ""), settings)
        if verdict:
            if verdict.blocked:
                emit(f"\n[tool] bash SANDBOX: {verdict.message}")
                return verdict.message
            emit(f"\n[sandbox] WARN: {verdict.message}")

    emit(f"\n[tool] {name}({json.dumps(args, ensure_ascii=False)[:120]})")
    result = await tools.execute(name, args)
    if len(result) < 500:
        emit(result)
    else:
        emit(result[:500] + "...")

    from meris.harness.event_hooks import run_event_hooks

    if name in ("write_file", "edit_file"):
        rel = str(args.get("path", ""))
        for hr in await run_event_hooks(workspace, settings, "onSave", path=rel):
            if hr.message:
                emit(f"\n[hook] onSave: {hr.message[:500]}")
            if hr.block:
                result += f"\n[onSave hook BLOCKED]\n{hr.message}"
                return result

    if name == "git_commit":
        for hr in await run_event_hooks(workspace, settings, "onCommit"):
            if hr.message:
                emit(f"\n[hook] onCommit: {hr.message[:500]}")

    if post_edit_cmds and name in ("write_file", "edit_file"):
        ok, sensor_out = await run_post_edit_sensors(workspace)
        if sensor_out:
            tag = "PASS" if ok else "FAIL"
            emit(f"\n[sensor] postEdit {tag}\n{sensor_out[:1500]}")
            if not ok:
                result += f"\n\n[postEdit sensor FAIL]\n{sensor_out[:2000]}"
                from meris.harness.check import is_harness_check_failure
                from meris.harness.ratchet.events import record_event

                kind = "harness_check_fail" if is_harness_check_failure(sensor_out) else "sensor_fail"
                record_event(
                    workspace,
                    kind,
                    detail=sensor_out[:800],
                    tool=name,
                    tags=["postEdit", name],
                )

    await hooks.run_post(name, args, result)
    return result
