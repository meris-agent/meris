"""Meris CLI — ask | plan | run | tui | mcp | session | parallel | init-harness | spec | doctor."""

from __future__ import annotations

import asyncio
import shutil
import signal
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from meris.env import load_env
from meris.harness.paths import harness_root
from meris.harness.sessions import delete_session, list_sessions, load_session, prune_sessions
from meris.loop import agent_loop
from meris.parallel import run_parallel

load_env()

app = typer.Typer(name="meris", help="Meris — harness-first coding agent")
tui_app = typer.Typer(help="Interactive TUI session")
mcp_app = typer.Typer(help="MCP server management")
session_app = typer.Typer(help="Session persistence")
spec_app = typer.Typer(help="Kiro-style spec workflow")
benchmark_app = typer.Typer(help="Benchmark task suite")
ratchet_app = typer.Typer(help="Harness self-evolution (Ratchet)")
insights_app = typer.Typer(help="Habit insights from session history (confirm → evolve)")
models_app = typer.Typer(help="LLM provider presets (multi-vendor)")
native_app = typer.Typer(help="Native Rust core (meris-rs)")
harness_app = typer.Typer(help="Harness validation")
app.add_typer(tui_app, name="tui")
app.add_typer(mcp_app, name="mcp")
app.add_typer(session_app, name="session")
app.add_typer(spec_app, name="spec")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(ratchet_app, name="ratchet")
ratchet_app.add_typer(insights_app, name="insights")
app.add_typer(models_app, name="models")
app.add_typer(native_app, name="native")
app.add_typer(harness_app, name="harness")

console = Console()


def _pkg_templates() -> Path:
    return Path(__file__).resolve().parent.parent / "templates"


def _make_approver() -> Callable[[str, dict], bool]:
    def approve(tool_name: str, args: dict) -> bool:
        console.print(f"\n[yellow]Approve tool[/yellow] [bold]{tool_name}[/bold]")
        console.print(f"  args: {args}")
        return typer.confirm("Run this tool?", default=False)

    return approve


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")


def _ratchet_after_run(workspace: Path, session_id: str | None = None) -> None:
    from meris.harness.ratchet import ratchet_post_run

    _, msg = ratchet_post_run(workspace, session_id=session_id)
    if msg:
        console.print(f"\n[dim]{msg}[/dim]")


async def _stream(
    task: str,
    workspace: Path,
    mode: str,
    *,
    max_turns: int = 30,
    run_sensors_at_end: bool = True,
    require_approval: bool = False,
    session_id: str | None = None,
    resume: bool = False,
    plan_output: str | Path | None = "__default__",
    ratchet: bool = False,
    event_stream_path: str | Path | None = None,
    json_output: bool = False,
) -> dict | None:
    from meris.harness.protocol import EventStream, emit_submission

    cancel = asyncio.Event()
    interrupted = False
    stream = EventStream.memory() if json_output else EventStream.open(event_stream_path)
    lines: list[str] = []
    result: dict = {"status": "unknown", "session": "", "lines": lines, "events": []}

    def _on_sigint(_signum, _frame) -> None:
        nonlocal interrupted
        if not cancel.is_set():
            interrupted = True
            cancel.set()
            emit_submission(stream, action="cancel", task=task[:200])
            if not json_output:
                console.print("\n[yellow]Ctrl+C — saving session, stopping after current step…[/yellow]")

    prev = signal.signal(signal.SIGINT, _on_sigint)
    kwargs: dict = {
        "max_turns": max_turns,
        "run_sensors_at_end": run_sensors_at_end,
        "require_approval": require_approval,
        "session_id": session_id,
        "resume": resume,
        "cancel": cancel,
        "plan_output": plan_output,
        "event_stream": stream,
    }
    if require_approval:
        kwargs["approve_fn"] = _make_approver()
    emit_submission(stream, action="user", task=task[:200])
    try:
        async for line in agent_loop(workspace, task, mode=mode, **kwargs):
            lines.append(line)
            if not json_output:
                console.print(line)
    finally:
        signal.signal(signal.SIGINT, prev)
        if stream:
            if stream.collector is not None:
                result["events"] = stream.collector
                for ev in reversed(stream.collector):
                    if ev.get("kind") == "done":
                        result["status"] = ev.get("status", "unknown")
                        result["session"] = ev.get("session", "")
                        break
                    if ev.get("kind") == "session_start":
                        result["session"] = result["session"] or ev.get("session", "")
            if not json_output:
                stream.close()
        if interrupted and not json_output:
            console.print("[dim]Resume with: meris session list → meris session resume <id>[/dim]")
        if ratchet:
            from meris.harness.sessions import list_sessions

            sid = session_id or result.get("session")
            if not sid:
                sessions = list_sessions(workspace)
                sid = sessions[0].id if sessions else None
            _ratchet_after_run(workspace, sid)
    if json_output:
        result["lines"] = lines
        return result
    return None


@models_app.command("list")
def models_list() -> None:
    """List built-in MERIS_PROVIDER presets and required API key env vars."""
    from meris.provider.presets import PRESETS, PRESET_ALIASES, list_preset_ids
    from meris.provider.resolve import resolve_provider_config

    table = Table("MERIS_PROVIDER", "Label", "Backend", "Default model", "API key (first wins)")
    for pid in list_preset_ids():
        p = PRESETS[pid]
        keys = ", ".join(p.api_key_env[:3])
        if len(p.api_key_env) > 3:
            keys += ", …"
        table.add_row(pid, p.label, p.backend, p.default_model, keys)
    console.print(table)
    alias_bits = ", ".join(f"{a}→{b}" for a, b in sorted(PRESET_ALIASES.items())[:8])
    console.print(f"\n[dim]Aliases (sample): {alias_bits}, …[/dim]")
    cfg = resolve_provider_config()
    console.print(
        f"\n[bold]Current env[/bold]: {cfg.preset_id} ({cfg.label}) · model={cfg.model}"
    )
    if cfg.backend == "openai_compat":
        console.print(f"  base_url={cfg.base_url}")
    console.print(
        "\n[dim]Set e.g. MERIS_PROVIDER=openai and OPENAI_API_KEY=sk-… "
        "(MERIS_BASE_URL / MERIS_MODEL override defaults).[/dim]"
    )


@models_app.command("show")
def models_show(
    provider: str = typer.Argument(..., help="Preset id, e.g. openai, deepseek, gemini"),
) -> None:
    """Show one preset and example env exports."""
    from meris.provider.presets import get_preset

    preset = get_preset(provider)
    if not preset:
        console.print(f"[red]Unknown preset: {provider}[/red]")
        console.print("[dim]Run: meris models list[/dim]")
        raise typer.Exit(1)
    console.print(f"[bold]{preset.label}[/bold] (MERIS_PROVIDER={preset.id})")
    console.print(f"  backend: {preset.backend}")
    if preset.base_url:
        console.print(f"  base_url: {preset.base_url}")
    console.print(f"  model: {preset.default_model}")
    console.print(f"  api_key_env: {', '.join(preset.api_key_env)}")
    if preset.docs_url:
        console.print(f"  docs: {preset.docs_url}")
    key = preset.api_key_env[0] if preset.api_key_env else "LLM_API_KEY"
    console.print("\n[bold]Example (bash)[/bold]")
    console.print(f"  export MERIS_PROVIDER={preset.id}")
    console.print(f"  export {key}=your-key-here")
    if preset.backend == "openai_compat":
        console.print(f"  export MERIS_BASE_URL={preset.base_url}")
        console.print(f"  export MERIS_MODEL={preset.default_model}")


@models_app.command("route")
def models_route(
    task: str = typer.Argument(..., help="Sample task text to match routing rules"),
    mode: str = typer.Option("run", "--mode", "-m", help="ask | plan | run"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Preview which provider/model settings routing would pick for a task."""
    from meris.provider.resolve import resolve_provider_config
    from meris.provider.router import resolve_task_routing

    ws = cwd.resolve()
    overrides, note = resolve_task_routing(ws, mode, task)
    cfg = resolve_provider_config(
        provider=overrides.get("provider"),
        model=overrides.get("model"),
        base_url=overrides.get("base_url"),
    )
    if note:
        console.print(f"[green]Routing[/green]: {note}")
    else:
        console.print("[dim]No models routing — using env / MERIS_PROVIDER only[/dim]")
    console.print(f"[bold]Resolved[/bold]: {cfg.preset_id} · model={cfg.model}")
    if cfg.backend == "openai_compat":
        console.print(f"  base_url={cfg.base_url}")


@app.command("doctor")
def doctor_cmd(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    no_probe: bool = typer.Option(False, "--no-probe", help="Skip live API call"),
) -> None:
    """Check API key, model, harness files, and optional API probe."""
    from meris.harness.doctor import run_doctor

    results = _run_async(run_doctor(cwd.resolve(), probe=not no_probe))
    table = Table("Check", "Status", "Detail")
    fails = 0
    for r in results:
        style = {"ok": "green", "warn": "yellow", "fail": "red"}.get(r.status, "white")
        table.add_row(r.name, f"[{style}]{r.status}[/{style}]", r.detail[:80])
        if r.status == "fail":
            fails += 1
    console.print(table)
    if fails:
        raise typer.Exit(1)


@harness_app.command("check")
def harness_check_cmd(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Static harness checks (paths, imports). Exit 1 on failure."""
    from meris.harness.check import harness_check_failed, run_harness_check

    results = run_harness_check(cwd.resolve())
    table = Table("Check", "Status", "Detail")
    for r in results:
        style = "green" if r.ok else "red"
        table.add_row(r.name, f"[{style}]{'ok' if r.ok else 'fail'}[/]", r.detail[:70])
        if not r.ok and r.hint:
            console.print(f"  [dim]hint:[/dim] {r.hint}")
    console.print(table)
    if harness_check_failed(results):
        raise typer.Exit(1)


@app.command("version")
def version_cmd() -> None:
    """Print package version."""
    console.print(f"meris-agent {version('meris-agent')}")


@app.command("init-harness")
def init_harness(
    workspace: Path = typer.Argument(Path.cwd(), help="Target repository"),
) -> None:
    """Install AGENTS.md, PROGRESS.md, .meris/settings.yaml into a repo."""
    ws = workspace.resolve()
    tpl = _pkg_templates()

    agents = ws / "AGENTS.md"
    if not agents.exists():
        shutil.copy(tpl / "AGENTS.md", agents)
        console.print(f"[green]Created[/green] {agents}")

    progress = ws / "PROGRESS.md"
    if not progress.exists():
        shutil.copy(tpl / "PROGRESS.md", progress)
        console.print(f"[green]Created[/green] {progress}")

    from meris.harness.paths import HARNESS_DIR

    harness = ws / HARNESS_DIR
    harness.mkdir(exist_ok=True)
    (harness / "sessions").mkdir(exist_ok=True)
    (harness / "plan").mkdir(exist_ok=True)
    (harness / "ratchet" / "proposals").mkdir(parents=True, exist_ok=True)
    (harness / "ratchet" / "applied").mkdir(parents=True, exist_ok=True)
    skills_dir = harness / "skills"
    rules_dir = harness / "rules"
    rules_dir.mkdir(exist_ok=True)
    skills_dir.mkdir(exist_ok=True)
    sample_skill = skills_dir / "harness.md"
    if not sample_skill.exists() and (tpl / "skills" / "harness.md").exists():
        shutil.copy(tpl / "skills" / "harness.md", sample_skill)
        console.print(f"[green]Created[/green] {sample_skill}")

    for rule_name in ("paths.md", "workspace.md"):
        rule_dst = rules_dir / rule_name
        rule_src = tpl / "rules" / rule_name
        if not rule_dst.exists() and rule_src.is_file():
            shutil.copy(rule_src, rule_dst)
            console.print(f"[green]Created[/green] {rule_dst}")

    settings_yaml = harness / "settings.yaml"
    settings_json = harness / "settings.json"
    if not settings_yaml.exists() and not settings_json.exists():
        src = tpl / "settings.example.yaml"
        if src.is_file():
            shutil.copy(src, settings_yaml)
            console.print(f"[green]Created[/green] {settings_yaml}")
        elif (tpl / "settings.json").is_file():
            shutil.copy(tpl / "settings.json", settings_json)
            console.print(f"[green]Created[/green] {settings_json}")

    docs_harness = ws / "docs" / "harness"
    tpl_docs = tpl / "docs" / "harness"
    if tpl_docs.is_dir() and not docs_harness.exists():
        shutil.copytree(tpl_docs, docs_harness)
        console.print(f"[green]Created[/green] {docs_harness}/")

    console.print("[bold]Harness initialized.[/bold] Edit AGENTS.md for your stack.")
    console.print("[dim]Next: meris ratchet learn --init[/dim]")


@spec_app.command("init")
def spec_init_cmd(
    feature: str = typer.Argument(..., help="Feature name"),
    workspace: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Init Kiro-style spec (requirements / design / tasks)."""
    from meris.harness.spec import init_spec

    tpl = _pkg_templates() / "spec"
    d = init_spec(workspace.resolve(), feature, tpl_dir=tpl if tpl.is_dir() else None)
    console.print(f"[green]Spec initialized at[/green] {d}")


@spec_app.command("status")
def spec_status_cmd(
    workspace: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Show spec phase status."""
    from meris.harness.spec import spec_status

    rows = spec_status(workspace.resolve())
    table = Table("Phase", "Status", "Detail")
    for phase, status, detail in rows:
        table.add_row(phase, status, detail)
    console.print(table)


@spec_app.command("next")
def spec_next_cmd(
    note: str = typer.Option("", "--note", "-n", help="Extra context for this phase"),
    workspace: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    max_turns: int = typer.Option(12, "--max-turns"),
) -> None:
    """Run agent to fill the next incomplete spec phase."""
    from meris.harness.spec import (
        build_spec_task,
        get_next_phase,
        mark_phase_complete,
        spec_dir,
    )

    ws = workspace.resolve()
    if not spec_dir(ws).is_dir():
        console.print("[red]No spec found. Run: meris spec init <feature>[/red]")
        raise typer.Exit(1)

    phase = get_next_phase(ws)
    if phase is None:
        console.print("[green]Spec complete — all phases done.[/green]")
        return

    console.print(f"[bold]Next phase:[/bold] {phase.name} → {phase.path.name}")
    task = build_spec_task(phase, note)

    async def _go() -> None:
        async for line in agent_loop(
            ws,
            task,
            mode="plan",
            max_turns=max_turns,
            run_sensors_at_end=False,
            plan_output=phase.path,
        ):
            console.print(line)
        text = phase.path.read_text(encoding="utf-8") if phase.path.is_file() else ""
        from meris.harness.spec import phase_is_complete

        if text and phase_is_complete(text):
            mark_phase_complete(ws, phase.name)
            console.print(f"[green]Phase {phase.name} marked complete.[/green]")
        else:
            console.print(f"[yellow]Phase {phase.name} still incomplete — edit or re-run.[/yellow]")

    _run_async(_go())


@app.command("spec")
def spec_init_legacy(
    feature: str = typer.Argument(..., help="Feature name (alias for spec init)"),
    workspace: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Legacy alias: meris spec <feature> → spec init."""
    spec_init_cmd(feature, workspace)


@app.command("ask")
def ask_cmd(
    task: str = typer.Argument(...),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    session_id: str | None = typer.Option(None, "--session-id"),
    ratchet: bool = typer.Option(
        False, "--ratchet", help="After run: refresh profile + scan for harness proposals"
    ),
    event_stream: Path | None = typer.Option(
        None, "--event-stream", help="Append JSONL events to path (- for stdout)"
    ),
) -> None:
    """Read-only exploration (Cursor Ask mode)."""
    _run_async(
        _stream(
            task,
            cwd.resolve(),
            "ask",
            session_id=session_id,
            plan_output=None,
            ratchet=ratchet,
            event_stream_path=event_stream,
        )
    )


@app.command("plan")
def plan_cmd(
    task: str = typer.Argument(...),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    session_id: str | None = typer.Option(None, "--session-id"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Plan output path"),
    no_save: bool = typer.Option(False, "--no-save", help="Do not write tasks.md"),
    ratchet: bool = typer.Option(False, "--ratchet", help="After run: refresh profile + scan proposals"),
    event_stream: Path | None = typer.Option(None, "--event-stream", help="JSONL event log path"),
) -> None:
    """Generate plan / tasks without editing code (Cursor Plan + Kiro tasks)."""
    plan_out: str | Path | None = None if no_save else (out or "__default__")
    _run_async(
        _stream(
            task,
            cwd.resolve(),
            "plan",
            session_id=session_id,
            plan_output=plan_out,
            ratchet=ratchet,
            event_stream_path=event_stream,
        )
    )


@app.command("review")
def review_cmd(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    staged: bool = typer.Option(False, "--staged", help="Review staged diff only"),
    max_turns: int = typer.Option(12, "--max-turns"),
    event_stream: Path | None = typer.Option(None, "--event-stream"),
) -> None:
    """Read-only code review of git diff (markdown checklist output)."""
    from meris.harness.review import build_review_task

    ws = cwd.resolve()
    try:
        task = build_review_task(ws, staged=staged)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    _run_async(
        _stream(
            task,
            ws,
            "review",
            max_turns=max_turns,
            run_sensors_at_end=False,
            plan_output=None,
            event_stream_path=event_stream,
        )
    )


@app.command("exec")
def exec_cmd(
    task: str = typer.Argument(...),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    mode: str = typer.Option("run", "--mode", "-m", help="run | ask | plan | review"),
    max_turns: int = typer.Option(30, "--max-turns"),
    json_out: bool = typer.Option(False, "--json", help="Print JSON result on stdout"),
    no_sensor: bool = typer.Option(False, "--no-sensor"),
) -> None:
    """Headless agent run for CI/scripts (optional --json)."""
    import json as json_mod

    out = _run_async(
        _stream(
            task,
            cwd.resolve(),
            mode,
            max_turns=max_turns,
            run_sensors_at_end=not no_sensor and mode == "run",
            plan_output=None if mode != "plan" else "__default__",
            json_output=json_out,
        )
    )
    if json_out and out is not None:
        console.print(json_mod.dumps(out, ensure_ascii=False, indent=2))


@app.command("run")
def run_cmd(
    task: str = typer.Argument(...),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    max_turns: int = typer.Option(30, "--max-turns"),
    approve: bool = typer.Option(False, "--approve", help="Confirm each mutating tool"),
    no_sensor: bool = typer.Option(False, "--no-sensor", help="Skip DoD sensors at end"),
    session_id: str | None = typer.Option(None, "--session-id", help="Optional session id"),
    from_plan: bool = typer.Option(
        False, "--from-plan", help="Prepend .meris/plan/tasks.md to task"
    ),
    from_spec: bool = typer.Option(
        False, "--from-spec", help="Prepend .meris/spec/tasks.md to task"
    ),
    ratchet: bool = typer.Option(
        False,
        "--ratchet",
        help="After run: refresh profile + scan for harness proposals",
    ),
    event_stream: Path | None = typer.Option(None, "--event-stream", help="JSONL event log path"),
) -> None:
    """Full agent loop with tools + sensors (default mode)."""
    ws = cwd.resolve()
    hroot = harness_root(ws)
    task_text = task
    if from_plan:
        plan_file = hroot / "plan" / "tasks.md"
        if plan_file.is_file():
            task_text = f"Implement this plan:\n\n{plan_file.read_text(encoding='utf-8')}\n\n---\n{task}"
        else:
            console.print(f"[yellow]Warning:[/yellow] {plan_file} not found")
    if from_spec:
        spec_tasks = hroot / "spec" / "tasks.md"
        if spec_tasks.is_file():
            ctx = spec_tasks.read_text(encoding="utf-8")
            task_text = f"Implement spec tasks:\n\n{ctx}\n\n---\n{task_text}"
        else:
            console.print(f"[yellow]Warning:[/yellow] {spec_tasks} not found")
    _run_async(
        _stream(
            task_text,
            ws,
            "run",
            max_turns=max_turns,
            run_sensors_at_end=not no_sensor,
            require_approval=approve,
            session_id=session_id,
            plan_output=None,
            ratchet=ratchet,
            event_stream_path=event_stream,
        )
    )


@app.command("parallel")
def parallel_cmd(
    tasks: list[str] = typer.Argument(None, help="One or more tasks"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    mode: str = typer.Option("ask", "--mode", "-m", help="ask | plan | run"),
    concurrency: int = typer.Option(3, "--concurrency", "-j"),
    isolate: bool = typer.Option(False, "--isolate", help="Git worktree per run session"),
    max_turns: int = typer.Option(20, "--max-turns"),
    file: Path | None = typer.Option(None, "--file", "-f", help="Task list file (one per line)"),
) -> None:
    """Run multiple agent sessions in parallel."""
    ws = cwd.resolve()
    all_tasks = list(tasks or [])
    if file:
        all_tasks.extend(
            ln.strip()
            for ln in file.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        )
    if not all_tasks:
        console.print("[red]No tasks provided[/red]")
        raise typer.Exit(1)

    async def _go() -> None:
        results = await run_parallel(
            ws,
            all_tasks,
            mode=mode,
            max_concurrency=concurrency,
            isolate=isolate,
            max_turns=max_turns,
            on_line=lambda i, line: console.print(line),
        )
        console.print(f"\n[bold]Done: {len(results)} sessions[/bold]")
        for r in results:
            console.print(f"  [{r.index}] {r.session_id} — {r.status}: {r.task[:60]}")

    _run_async(_go())


@session_app.command("list")
def session_list(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """List saved sessions."""
    records = list_sessions(cwd.resolve())
    if not records:
        console.print("(no sessions)")
        return
    table = Table("ID", "Status", "Mode", "Turn", "Task")
    for r in records[:20]:
        table.add_row(r.id, r.status, r.mode, str(r.turn), r.task[:50])
    console.print(table)


@session_app.command("show")
def session_show(
    session_id: str = typer.Argument(...),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Show session details."""
    rec = load_session(cwd.resolve(), session_id)
    if not rec:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)
    console.print(f"ID: {rec.id}\nStatus: {rec.status}\nMode: {rec.mode}\nTurn: {rec.turn}")
    console.print(f"Task: {rec.task}\nMessages: {len(rec.messages)}")


@session_app.command("resume")
def session_resume(
    session_id: str = typer.Argument(...),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    approve: bool = typer.Option(False, "--approve"),
) -> None:
    """Resume a saved session."""
    rec = load_session(cwd.resolve(), session_id)
    if not rec:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)
    _run_async(
        _stream(
            rec.task,
            cwd.resolve(),
            rec.mode,
            max_turns=rec.max_turns,
            require_approval=approve,
            session_id=session_id,
            resume=True,
            plan_output=None,
        )
    )


@session_app.command("delete")
def session_delete(
    session_id: str = typer.Argument(...),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Delete a saved session."""
    ok = delete_session(cwd.resolve(), session_id)
    if not ok:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Deleted session {session_id}[/green]")


@session_app.command("prune")
def session_prune(
    keep: int = typer.Option(20, "--keep", "-k", help="Sessions to retain"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Delete oldest sessions beyond keep count."""
    n = prune_sessions(cwd.resolve(), keep=keep)
    console.print(f"[green]Pruned {n} session(s)[/green]")


@benchmark_app.command("run")
def benchmark_run(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    tasks_file: Path = typer.Option(
        None,
        "--file",
        "-f",
        help="Benchmark tasks JSON (default: scripts/benchmark/tasks.json)",
    ),
    filter: str | None = typer.Option(
        None,
        "--filter",
        help="Run only task id matching this string (prefix or exact)",
    ),
) -> None:
    """Run benchmark tasks and report pass rate."""
    from meris.benchmark import load_benchmark_tasks, run_benchmark, summarize

    ws = cwd.resolve()
    tf = tasks_file or (Path(__file__).resolve().parent.parent / "scripts" / "benchmark" / "tasks.json")
    if not tf.is_file():
        console.print(f"[red]Tasks file not found: {tf}[/red]")
        raise typer.Exit(1)
    tasks = load_benchmark_tasks(tf)
    console.print(f"[bold]Running {len(tasks)} benchmark tasks…[/bold]")

    if filter:
        tasks = [t for t in tasks if t.id == filter or t.id.startswith(filter)]
        if not tasks:
            console.print(f"[red]No tasks match filter: {filter}[/red]")
            raise typer.Exit(1)

    async def _go():
        return await run_benchmark(
            ws,
            tasks,
            on_line=lambda tid, line: console.print(f"[{tid}] {line}"),
            task_filter=filter,
        )

    results = _run_async(_go())
    summary = summarize(results)
    table = Table("Task", "Status", "Detail")
    for r in results:
        style = "green" if r.status == "pass" else "red"
        table.add_row(r.task_id, f"[{style}]{r.status}[/{style}]", r.detail[:60])
    console.print(table)
    console.print(
        f"\n[bold]Pass rate: {summary['passed']}/{summary['total']} "
        f"({summary['rate']:.0f}%)[/bold]"
    )
    if summary["failed"]:
        from meris.harness.ratchet import scan_workspace

        created = scan_workspace(ws, since_days=1)
        if created:
            console.print(f"[ratchet] {len(created)} new proposal(s) — meris ratchet review")
        else:
            console.print("[dim]Harness: meris ratchet scan → meris ratchet review[/dim]")
        raise typer.Exit(1)


@benchmark_app.command("list")
def benchmark_list(
    tasks_file: Path = typer.Option(None, "--file", "-f"),
) -> None:
    """List benchmark tasks."""
    from meris.benchmark import load_benchmark_tasks

    tf = tasks_file or (Path(__file__).resolve().parent.parent / "scripts" / "benchmark" / "tasks.json")
    tasks = load_benchmark_tasks(tf)
    table = Table("ID", "Mode", "Task")
    for t in tasks:
        table.add_row(t.id, t.mode, t.task[:60])
    console.print(table)


@ratchet_app.command("status")
def ratchet_status(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    since_days: int = typer.Option(7, "--since"),
) -> None:
    """Show ratchet events, pending proposals, and pending insights."""
    from meris.harness.ratchet import count_events, count_pending_insights, list_proposals
    from meris.harness.ratchet.paths import events_file

    ws = cwd.resolve()
    pending = list_proposals(ws, status="pending")
    n_insights = count_pending_insights(ws)
    counts = count_events(ws, since_days=since_days)
    console.print(f"Events ({since_days}d): {events_file(ws).is_file()}")
    if counts:
        for kind, n in sorted(counts.items()):
            console.print(f"  {kind}: {n}")
    else:
        console.print("  [dim]none[/dim]")
    console.print(f"Pending proposals: {len(pending)}")
    for p in pending[:5]:
        console.print(f"  {p.id} [{p.lesson}] {p.summary[:40]}")
    console.print(f"Pending insights: {n_insights}")
    if n_insights:
        console.print("  [dim]meris ratchet insights review[/dim]")


@ratchet_app.command("learn")
def ratchet_learn(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    init: bool = typer.Option(
        False,
        "--init",
        help="Run even when no strong repo markers (right after init-harness)",
    ),
) -> None:
    """Scan project layout and create harness proposals (rules + optional AGENTS DoD)."""
    from meris.harness.ratchet import run_learn, scan_project

    ws = cwd.resolve()
    facts = scan_project(ws)
    console.print(
        f"[dim]Detected: {facts.package_manager}, dirs={', '.join(facts.top_dirs) or '—'}[/dim]"
    )
    created = run_learn(ws, init=init, save=True)
    if not created:
        console.print("[yellow]No new learn proposals[/yellow]")
        return
    for p in created:
        console.print(f"[green]+[/green] {p.id} [{p.lesson}] {p.summary}")
        if p.target.path == "AGENTS.md":
            console.print("    [yellow]apply needs --force-agents[/yellow]")
    console.print("\n[bold]meris ratchet review[/bold]")


@ratchet_app.command("profile")
def ratchet_profile(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    since_days: int = typer.Option(30, "--since"),
    show: bool = typer.Option(False, "--show", help="Print profile after rebuild"),
) -> None:
    """Rebuild `.meris/profile.md` from approve/permission events."""
    from meris.harness.ratchet import rebuild_profile
    from meris.harness.ratchet.profile import load_profile_text

    ws = cwd.resolve()
    path = rebuild_profile(ws, since_days=since_days)
    if not path:
        console.print("[dim]No approve/permission events — profile unchanged[/dim]")
        raise typer.Exit(0)
    console.print(f"[green]Updated[/green] {path}")
    if show:
        console.print(load_profile_text(ws))


@ratchet_app.command("analyze")
def ratchet_analyze(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    session_id: str | None = typer.Option(None, "--session-id", help="Session to analyze"),
    last_fail: bool = typer.Option(
        False, "--last-fail", help="Use latest failed session or event"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print prompt only, no API"),
    since_days: int = typer.Option(14, "--since"),
) -> None:
    """LLM analysis → harness proposals (JSON). Requires API key."""
    from meris.harness.ratchet.analyze import analyze_workspace, build_analyze_prompt, resolve_analyze_session
    from meris.provider import ProviderError

    ws = cwd.resolve()
    session = resolve_analyze_session(ws, session_id=session_id, last_fail=last_fail)
    if dry_run:
        console.print(build_analyze_prompt(ws, session=session, since_days=since_days))
        return

    async def _go():
        return await analyze_workspace(
            ws,
            session_id=session.id if session else None,
            last_fail=False,
            save=True,
            since_days=since_days,
        )

    try:
        created = _run_async(_go())
    except ProviderError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    if not created:
        console.print("[yellow]No valid proposals parsed[/yellow]")
        raise typer.Exit(1)
    for p in created:
        console.print(f"[green]+[/green] {p.id} [{p.lesson}] {p.summary}")
        if p.target.path == "AGENTS.md":
            console.print("    [yellow]apply needs --force-agents[/yellow]")
    console.print("\n[bold]meris ratchet review[/bold]")


@ratchet_app.command("scan")
def ratchet_scan(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    since_days: int = typer.Option(7, "--since", help="Only events within N days"),
    ingest_sessions: bool = typer.Option(
        False, "--ingest-sessions", help="Backfill events from failed sessions"
    ),
) -> None:
    """Scan events and create pending harness proposals."""
    from meris.harness.ratchet import scan_workspace

    ws = cwd.resolve()
    created = scan_workspace(ws, since_days=since_days, ingest_sessions=ingest_sessions)
    if not created:
        console.print("[yellow]No new proposals[/yellow]")
        return
    for p in created:
        console.print(f"[green]+[/green] {p.id} [{p.lesson}] {p.summary}")
        console.print(f"    → {p.target.path}")
    console.print(f"\n[bold]{len(created)} proposal(s)[/bold] — meris ratchet review")


@ratchet_app.command("digest")
def ratchet_digest(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    since_days: int = typer.Option(30, "--since", help="Scan user messages within N days"),
    min_sessions: int = typer.Option(2, "--min-sessions", help="Min distinct sessions per theme"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print candidates only, do not save"),
    llm: bool = typer.Option(False, "--llm", help="Also call LLM for extra insights (needs API)"),
) -> None:
    """Mine session history for repeated user habits → insight candidates."""
    from meris.harness.ratchet.digest import digest_sessions_rule_based, format_digest_report
    from meris.harness.ratchet.digest_llm import build_digest_llm_prompt
    from meris.provider import ProviderError

    ws = cwd.resolve()
    if dry_run and llm:
        console.print(build_digest_llm_prompt(ws, since_days=since_days))
        return

    if dry_run:
        created = digest_sessions_rule_based(
            ws, since_days=since_days, min_sessions=min_sessions
        )
        console.print(format_digest_report(created))
        return

    async def _go():
        from meris.harness.ratchet.digest import digest_workspace_async

        return await digest_workspace_async(
            ws,
            since_days=since_days,
            min_sessions=min_sessions,
            save=True,
            use_llm=llm,
        )

    try:
        if llm:
            created = _run_async(_go())
        else:
            from meris.harness.ratchet import digest_workspace

            created = digest_workspace(
                ws,
                since_days=since_days,
                min_sessions=min_sessions,
                save=True,
                use_llm=False,
            )
    except ProviderError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    if not created:
        console.print("[yellow]No new insights[/yellow]")
        console.print("[dim]Passive Ratchet (scan/analyze) unchanged — still use on failures[/dim]")
        return
    for ins in created:
        console.print(f"[green]+[/green] {ins.id} [{ins.lesson}] ×{ins.count}")
        console.print(f"    {ins.question[:70]}")
    console.print("\n[bold]meris ratchet insights review[/bold]")


@insights_app.command("list")
def ratchet_insights_list(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    all_status: bool = typer.Option(False, "--all", help="Include dismissed/accepted"),
) -> None:
    """List habit insight candidates."""
    from meris.harness.ratchet import list_insights

    ws = cwd.resolve()
    if all_status:
        rows: list = []
        for st in ("pending", "accepted", "dismissed"):
            rows.extend(list_insights(ws, status=st))
    else:
        rows = list_insights(ws, status="pending")
    if not rows:
        console.print("[dim]No insights[/dim]")
        return
    table = Table("ID", "Kind", "Status", "×", "Question")
    for ins in rows:
        table.add_row(
            ins.id,
            ins.kind,
            ins.status,
            str(ins.count),
            ins.question[:50],
        )
    console.print(table)


@insights_app.command("show")
def ratchet_insights_show(
    insight_id: str = typer.Argument(..., help="Insight id"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Show insight details and proposed harness content."""
    from meris.harness.ratchet import load_insight

    ins = load_insight(cwd.resolve(), insight_id)
    if not ins:
        console.print(f"[red]Not found: {insight_id}[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{ins.id}[/bold] [{ins.lesson}] {ins.status}")
    console.print(ins.question)
    console.print(f"Pattern: {ins.pattern}")
    console.print(f"Sessions ({ins.count}): {', '.join(ins.evidence[:6])}")
    console.print(f"Target: {ins.suggested_target}")
    console.print("\n[bold]Harness content if accepted:[/bold]")
    console.print(ins.suggested_content)


@insights_app.command("review")
def ratchet_insights_review(
    insight_id: str | None = typer.Argument(None, help="Insight id (optional)"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    apply_now: bool = typer.Option(
        True, "--apply/--no-apply", help="After accept, apply harness patch immediately"
    ),
) -> None:
    """Review pending insights; accept creates proposal (and optional apply)."""
    from meris.harness.ratchet import accept_insight, dismiss_insight, list_insights, load_insight

    ws = cwd.resolve()
    if insight_id:
        one = load_insight(ws, insight_id)
        items = [one] if one and one.status == "pending" else []
    else:
        items = list_insights(ws, status="pending")
    if not items:
        console.print("[dim]No pending insights[/dim]")
        return
    for ins in items:
        console.print(f"\n[bold]{ins.id}[/bold] [{ins.lesson}] ×{ins.count}")
        console.print(ins.question)
        console.print(ins.suggested_content[:350] + ("…" if len(ins.suggested_content) > 350 else ""))
        if typer.confirm("Write to Harness?", default=False):
            proposal = accept_insight(ws, ins.id)
            if not proposal:
                console.print("[red]Accept failed[/red]")
                continue
            console.print(f"[green]Proposal[/green] {proposal.id} → {proposal.target.path}")
            if apply_now and typer.confirm("Apply now?", default=True):
                _ratchet_apply_one(ws, proposal, verify=False)
            else:
                console.print("[dim]meris ratchet apply[/dim] " + proposal.id)
        elif typer.confirm("Dismiss (won't ask again)?", default=False):
            dismiss_insight(ws, ins.id)
            console.print("[dim]Dismissed[/dim]")
        else:
            console.print("[dim]Skipped[/dim]")


@insights_app.command("dismiss")
def ratchet_insights_dismiss(
    insight_id: str = typer.Argument(..., help="Insight id"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Dismiss an insight without writing harness."""
    from meris.harness.ratchet import dismiss_insight

    if dismiss_insight(cwd.resolve(), insight_id):
        console.print(f"[yellow]Dismissed {insight_id}[/yellow]")
    else:
        console.print(f"[red]Not found or not pending: {insight_id}[/red]")
        raise typer.Exit(1)


@insights_app.command("accept")
def ratchet_insights_accept(
    insight_id: str = typer.Argument(..., help="Insight id"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    apply_now: bool = typer.Option(False, "--apply", help="Apply harness patch immediately"),
) -> None:
    """Accept insight → pending Ratchet proposal."""
    from meris.harness.ratchet import accept_insight

    ws = cwd.resolve()
    proposal = accept_insight(ws, insight_id)
    if not proposal:
        console.print(f"[red]Not found or not pending: {insight_id}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Proposal[/green] {proposal.id} → {proposal.target.path}")
    if apply_now:
        _ratchet_apply_one(ws, proposal, verify=False)
    else:
        console.print("[dim]meris ratchet apply[/dim] " + proposal.id)


@ratchet_app.command("list")
def ratchet_list(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    all_status: bool = typer.Option(False, "--all", help="Include applied proposals"),
) -> None:
    """List ratchet proposals."""
    from meris.harness.ratchet import list_proposals

    status = None if all_status else "pending"
    props = list_proposals(cwd.resolve(), status=status)
    if not props:
        console.print("[dim]No proposals[/dim]")
        return
    table = Table("ID", "Lesson", "Status", "Summary")
    for p in props:
        table.add_row(p.id, p.lesson, p.status, p.summary[:50])
    console.print(table)


@ratchet_app.command("show")
def ratchet_show(
    proposal_id: str = typer.Argument(..., help="Proposal id"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Show proposal details and patch preview."""
    from meris.harness.ratchet import load_proposal

    p = load_proposal(cwd.resolve(), proposal_id)
    if not p:
        console.print(f"[red]Not found: {proposal_id}[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{p.id}[/bold] [{p.lesson}] {p.status}")
    console.print(p.summary)
    console.print(f"Target: {p.target.path} ({p.target.action})")
    if p.verify:
        console.print("Verify: " + ", ".join(p.verify))
    console.print("\n[bold]Content to apply:[/bold]")
    console.print(p.target.content)


@ratchet_app.command("review")
def ratchet_review(
    proposal_id: str | None = typer.Argument(None, help="Proposal id (optional)"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    verify: bool = typer.Option(False, "--verify", help="Run verify after apply"),
) -> None:
    """Review pending proposal(s); apply on confirm."""
    from meris.harness.ratchet import list_proposals, load_proposal, reject_proposal

    ws = cwd.resolve()
    if proposal_id:
        props = [load_proposal(ws, proposal_id)]
        props = [p for p in props if p and p.status == "pending"]
    else:
        props = list_proposals(ws, status="pending")
    if not props:
        console.print("[dim]No pending proposals[/dim]")
        return
    for p in props:
        console.print(f"\n[bold]{p.id}[/bold] [{p.lesson}] — {p.summary}")
        console.print(f"  → {p.target.path}")
        console.print(p.target.content[:400] + ("…" if len(p.target.content) > 400 else ""))
        if typer.confirm("Apply?", default=True):
            _ratchet_apply_one(ws, p, verify=verify)
        elif typer.confirm("Reject this proposal?", default=False):
            reject_proposal(ws, p.id)
            console.print("[dim]Rejected[/dim]")
        else:
            console.print("[dim]Skipped[/dim]")


@ratchet_app.command("reject")
def ratchet_reject(
    proposal_id: str = typer.Argument(..., help="Proposal id"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Reject a pending proposal without applying."""
    from meris.harness.ratchet import reject_proposal

    if reject_proposal(cwd.resolve(), proposal_id):
        console.print(f"[yellow]Rejected {proposal_id}[/yellow]")
    else:
        console.print(f"[red]Not found or not pending: {proposal_id}[/red]")
        raise typer.Exit(1)


@ratchet_app.command("apply")
def ratchet_apply(
    proposal_id: str = typer.Argument(..., help="Proposal id"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    verify: bool = typer.Option(False, "--verify", help="Run proposal verify commands"),
    force_agents: bool = typer.Option(False, "--force-agents", help="Allow AGENTS.md patches"),
    force_settings: bool = typer.Option(
        False, "--force-settings", help="Allow .meris/settings.* patches"
    ),
) -> None:
    """Apply a pending proposal to harness files."""
    from meris.harness.ratchet import load_proposal

    ws = cwd.resolve()
    p = load_proposal(ws, proposal_id)
    if not p or p.status != "pending":
        console.print(f"[red]Pending proposal not found: {proposal_id}[/red]")
        raise typer.Exit(1)
    _ratchet_apply_one(ws, p, verify=verify, force_agents=force_agents, force_settings=force_settings)


@ratchet_app.command("revert")
def ratchet_revert(
    proposal_id: str = typer.Argument(..., help="Applied proposal id"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """Restore harness files from apply backup."""
    from meris.harness.ratchet import revert_proposal

    if revert_proposal(cwd.resolve(), proposal_id):
        console.print(f"[green]Reverted {proposal_id}[/green]")
    else:
        console.print(f"[red]No backup for {proposal_id}[/red]")
        raise typer.Exit(1)


def _ratchet_apply_one(
    workspace: Path,
    proposal,
    *,
    verify: bool = False,
    force_agents: bool = False,
    force_settings: bool = False,
) -> None:
    from meris.harness.ratchet import apply_proposal

    try:
        dest = apply_proposal(
            workspace,
            proposal,
            force_agents=force_agents,
            force_settings=force_settings,
        )
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    console.print(f"[green]Applied[/green] → {dest}")
    if verify and proposal.verify:
        for cmd in proposal.verify:
            console.print(f"[dim]verify: {cmd}[/dim]")
            if cmd.startswith("meris benchmark"):
                parts = cmd.split()
                filt = None
                if "--filter" in parts:
                    filt = parts[parts.index("--filter") + 1]
                benchmark_run(
                    cwd=workspace,
                    tasks_file=None,
                    filter=filt,
                )


@tui_app.callback(invoke_without_command=True)
def tui_cmd(
    ctx: typer.Context,
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    mode: str = typer.Option("run", "--mode", "-m", help="ask | plan | run"),
    approve: bool = typer.Option(False, "--approve", help="Confirm mutating tools in TUI"),
    max_turns: int = typer.Option(30, "--max-turns"),
) -> None:
    """Launch interactive Textual TUI (REPL-style task input + log)."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        from meris.tui import run_tui
    except ImportError:
        console.print("[red]TUI requires: pip install meris-agent[tui][/red]")
        raise typer.Exit(1) from None
    run_tui(cwd.resolve(), mode=mode, approve=approve, max_turns=max_turns)


@mcp_app.command("list")
def mcp_list(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
) -> None:
    """List tools from configured MCP servers."""
    from meris.tui.app import list_mcp_tools

    lines = _run_async(list_mcp_tools(cwd.resolve()))
    for line in lines:
        console.print(line)


@native_app.command("status")
def native_status_cmd() -> None:
    """Show meris-rs binary availability."""
    from meris.native import native_status

    info = native_status()
    table = Table("Key", "Value")
    for k, v in info.items():
        table.add_row(k, str(v))
    console.print(table)
    if not info["available"]:
        console.print("[dim]Build: meris native build[/dim]")


@native_app.command("build")
def native_build_cmd(
    debug: bool = typer.Option(False, "--debug", help="Debug build instead of release"),
) -> None:
    """Build meris-rs with cargo (requires Rust toolchain)."""
    from meris.native import build_native

    code, out = build_native(release=not debug)
    if out:
        console.print(out)
    if code != 0:
        raise typer.Exit(code)
    console.print("[green]meris-rs built — native auto-enabled when binary present (MERIS_NATIVE=0 to disable)[/green]")


if __name__ == "__main__":
    app()
