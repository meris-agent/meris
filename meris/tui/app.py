"""Textual TUI for Meris Agent."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, RichLog, Static

from meris.harness.settings import load_settings
from meris.harness.sessions import list_sessions
from meris.loop import agent_loop
from meris.tools.mcp import MCP_AVAILABLE


class ApproveModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    ApproveModal { align: center middle; }
    #approve-box {
        width: 80; height: auto;
        border: thick $warning; background: $surface; padding: 1 2;
    }
    """

    def __init__(self, tool_name: str, args: dict) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.args = args

    def compose(self) -> ComposeResult:
        with Vertical(id="approve-box"):
            yield Label(f"Approve tool: [bold]{self.tool_name}[/bold]?")
            yield Static(str(self.args)[:500])
            yield Input(placeholder="y/n — type y to approve")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip().lower() in ("y", "yes"):
            self.dismiss(True)
        else:
            self.dismiss(False)


class MerisTUI(App):
    TITLE = "Meris Agent"
    SUB_TITLE = "Harness-first coding agent"
    CSS = """
    #main { height: 1fr; }
    #sessions-panel {
        width: 28;
        border: solid $secondary;
        height: 100%;
    }
    #log-panel { width: 1fr; }
    #log { height: 1fr; border: solid $primary; }
    #status { height: 3; padding: 0 1; }
    #task-input { dock: bottom; }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear_log", "Clear"),
        ("ctrl+r", "resume_session", "Resume"),
        ("ctrl+s", "refresh_sessions", "Sessions"),
        ("ctrl+enter", "submit_task", "Send"),
    ]

    def __init__(
        self,
        workspace: Path,
        *,
        mode: str = "run",
        approve: bool = False,
        max_turns: int = 30,
    ) -> None:
        super().__init__()
        self.workspace = workspace.resolve()
        self.mode = mode
        self.approve = approve
        self.max_turns = max_turns
        self._task_busy = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="status")
        with Horizontal(id="main"):
            with Vertical(id="sessions-panel"):
                yield Static("[bold]Sessions[/bold] (Enter to resume)")
                yield ListView(id="session-list")
            with Vertical(id="log-panel"):
                yield RichLog(id="log", wrap=True, highlight=True, markup=True)
        yield Input(
            placeholder="Enter task — Enter or Ctrl+Enter to send (CJK IME: Enter twice if needed)",
            id="task-input",
        )
        yield Footer()

    def on_mount(self) -> None:
        settings = load_settings(self.workspace)
        mcp = settings.get("mcpServers") or {}
        status = self.query_one("#status", Static)
        status.update(
            f"workspace={self.workspace.name}  mode={self.mode}  "
            f"approve={'on' if self.approve else 'off'}  mcp={len(mcp)} servers"
        )
        self.query_one("#task-input", Input).focus()
        log = self.query_one("#log", RichLog)
        log.write("[meris] Ready — type a task below, press Enter or Ctrl+Enter to send.")
        if not MCP_AVAILABLE and mcp:
            log.write("[yellow]Install MCP: pip install meris-agent[mcp][/yellow]")
        self._refresh_session_list()

    def _refresh_session_list(self) -> None:
        lv = self.query_one("#session-list", ListView)
        lv.clear()
        records = list_sessions(self.workspace)[:15]
        if not records:
            lv.append(ListItem(Label("(no sessions)"), disabled=True))
            return
        for rec in records:
            label = f"{rec.id[:8]} {rec.status[:4]} {rec.task[:18]}"
            item = ListItem(Label(label))
            item.session_id = rec.id  # type: ignore[attr-defined]
            item.resumable = rec.status in ("running", "cancelled", "error")  # type: ignore[attr-defined]
            lv.append(item)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        sid = getattr(item, "session_id", None)
        if not sid or self._task_busy:
            return
        log = self.query_one("#log", RichLog)
        log.write(f"[cyan]Resuming session {sid}…[/cyan]")
        from meris.harness.sessions import load_session

        rec = load_session(self.workspace, sid)
        if rec:
            await self._run_task(rec.task, session_id=sid, resume=True)

    def action_refresh_sessions(self) -> None:
        self._refresh_session_list()

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()

    async def action_resume_session(self) -> None:
        records = list_sessions(self.workspace)
        candidates = [r for r in records if r.status in ("running", "cancelled", "error")]
        log = self.query_one("#log", RichLog)
        if not candidates:
            log.write("[yellow]No resumable sessions[/yellow]")
            return
        rec = candidates[0]
        log.write(f"[cyan]Resuming {rec.id}…[/cyan]")
        await self._run_task(rec.task, session_id=rec.id, resume=True)

    async def _approve(self, tool_name: str, args: dict) -> bool:
        return await self.push_screen_wait(ApproveModal(tool_name, args))

    async def action_submit_task(self) -> None:
        """Submit task from input (Ctrl+Enter — reliable with CJK IME)."""
        await self._submit_task_from_input()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self._submit_task_from_input(event.input)

    async def _submit_task_from_input(self, inp: Input | None = None) -> None:
        if self._task_busy:
            return
        field = inp or self.query_one("#task-input", Input)
        task = field.value.strip()
        if not task:
            # IME may fire Enter with empty payload before composition finishes — keep text.
            return
        field.value = ""
        await self._run_task(task)

    async def _run_task(
        self,
        task: str,
        *,
        session_id: str | None = None,
        resume: bool = False,
    ) -> None:
        self._task_busy = True
        log = self.query_one("#log", RichLog)
        log.write(f"\n[bold cyan]>>> {task}[/bold cyan]")

        kwargs: dict = {
            "mode": self.mode,
            "max_turns": self.max_turns,
            "require_approval": self.approve,
            "session_id": session_id,
            "resume": resume,
            "plan_output": None,
        }
        if self.approve:
            kwargs["approve_fn"] = self._approve

        try:
            async for line in agent_loop(self.workspace, task, **kwargs):
                log.write(line)
        except Exception as e:
            log.write(f"[red]Error: {e}[/red]")
        finally:
            self._task_busy = False
            self._refresh_session_list()
            self.query_one("#task-input", Input).focus()


def run_tui(
    workspace: Path,
    *,
    mode: str = "run",
    approve: bool = False,
    max_turns: int = 30,
) -> None:
    app = MerisTUI(workspace, mode=mode, approve=approve, max_turns=max_turns)
    app.run()


async def list_mcp_tools(workspace: Path) -> list[str]:
    from meris.tools.mcp import MCPManager

    settings = load_settings(workspace)
    servers = settings.get("mcpServers") or {}
    if not servers:
        return ["(no mcpServers in .meris/settings.json)"]
    if not MCP_AVAILABLE:
        return ["Install MCP: pip install meris-agent[mcp]"]
    mgr, notes = await MCPManager.connect(servers)
    lines = list(notes)
    lines.extend(mgr.list_tools_summary())
    await mgr.close()
    return lines
