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
native_app = typer.Typer(help="Native Rust core (meris-rs)")
app.add_typer(tui_app, name="tui")
app.add_typer(mcp_app, name="mcp")
app.add_typer(session_app, name="session")
app.add_typer(spec_app, name="spec")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(native_app, name="native")

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
) -> None:
    cancel = asyncio.Event()
    interrupted = False

    def _on_sigint(_signum, _frame) -> None:
        nonlocal interrupted
        if not cancel.is_set():
            interrupted = True
            cancel.set()
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
    }
    if require_approval:
        kwargs["approve_fn"] = _make_approver()
    try:
        async for line in agent_loop(workspace, task, mode=mode, **kwargs):
            console.print(line)
    finally:
        signal.signal(signal.SIGINT, prev)
        if interrupted:
            console.print("[dim]Resume with: meris session list → meris session resume <id>[/dim]")


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


@app.command("version")
def version_cmd() -> None:
    """Print package version."""
    console.print(f"meris-agent {version('meris-agent')}")


@app.command("init-harness")
def init_harness(
    workspace: Path = typer.Argument(Path.cwd(), help="Target repository"),
) -> None:
    """Install AGENTS.md, PROGRESS.md, .meris/settings.json into a repo."""
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
    skills_dir = harness / "skills"
    skills_dir.mkdir(exist_ok=True)
    sample_skill = skills_dir / "harness.md"
    if not sample_skill.exists() and (tpl / "skills" / "harness.md").exists():
        shutil.copy(tpl / "skills" / "harness.md", sample_skill)
        console.print(f"[green]Created[/green] {sample_skill}")

    settings = harness / "settings.json"
    if not settings.exists():
        shutil.copy(tpl / "settings.json", settings)
        console.print(f"[green]Created[/green] {settings}")

    console.print("[bold]Harness initialized.[/bold] Edit AGENTS.md for your stack.")


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
) -> None:
    """Read-only exploration (Cursor Ask mode)."""
    _run_async(
        _stream(task, cwd.resolve(), "ask", session_id=session_id, plan_output=None)
    )


@app.command("plan")
def plan_cmd(
    task: str = typer.Argument(...),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C"),
    session_id: str | None = typer.Option(None, "--session-id"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Plan output path"),
    no_save: bool = typer.Option(False, "--no-save", help="Do not write tasks.md"),
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
        )
    )


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

    async def _go():
        return await run_benchmark(
            ws,
            tasks,
            on_line=lambda tid, line: console.print(f"[{tid}] {line}"),
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
    console.print("[green]meris-rs built — set MERIS_NATIVE=1 to use native context compress[/green]")


if __name__ == "__main__":
    app()
