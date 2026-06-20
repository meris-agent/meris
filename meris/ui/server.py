"""HTTP server for standalone Meris Agent Window (Phase H10)."""

from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXT_MEDIA = _REPO_ROOT / "extensions" / "vscode-meris" / "media"
_UI_STATIC = Path(__file__).resolve().parent / "static"


class UiRuntime:
    """Process + JSONL tail state for one workspace."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd.resolve()
        self.events_path = self.cwd / ".meris" / "events" / "agent-window.jsonl"
        self.approval_dir = self.cwd / ".meris" / "events" / "approval"
        self.tail_pos = 0
        self.proc: subprocess.Popen[str] | None = None
        self.stderr = ""
        self.lock = threading.Lock()
        self.subscribers: list[threading.Condition] = []
        self._stop_tail = threading.Event()
        self._tail_thread = threading.Thread(target=self._tail_loop, daemon=True)
        self._tail_thread.start()

    def subscribe(self) -> threading.Condition:
        cond = threading.Condition()
        with self.lock:
            self.subscribers.append(cond)
        return cond

    def unsubscribe(self, cond: threading.Condition) -> None:
        with self.lock:
            if cond in self.subscribers:
                self.subscribers.remove(cond)

    def broadcast(self, msg: dict[str, Any]) -> None:
        ui_broadcast(msg)

    def _read_new_events(self) -> list[dict[str, Any]]:
        path = self.events_path
        if not path.is_file():
            return []
        size = path.stat().st_size
        if size < self.tail_pos:
            self.tail_pos = 0
        if size == self.tail_pos:
            return []
        with path.open("r", encoding="utf-8") as fh:
            fh.seek(self.tail_pos)
            chunk = fh.read()
            self.tail_pos = fh.tell()
        events: list[dict[str, Any]] = []
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    def _tail_loop(self) -> None:
        while not self._stop_tail.is_set():
            for ev in self._read_new_events():
                enriched = _enrich_event(self.cwd, ev)
                self.broadcast({"type": "event", "event": enriched})
            time.sleep(0.2)

    def close(self) -> None:
        self._stop_tail.set()
        self.kill()

    def kill(self) -> None:
        with self.lock:
            proc = self.proc
            self.proc = None
        if proc and proc.poll() is None:
            proc.terminate()

    def _prepare_events_file(self) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_path.write_text("", encoding="utf-8")
        self.tail_pos = 0

    def spawn_run(
        self,
        *,
        task: str,
        mode: str,
        approve: bool,
        resume: bool,
        session_id: str,
        from_plan: bool = False,
        ratchet_after: bool = False,
    ) -> None:
        self.kill()
        self.stderr = ""
        self._prepare_events_file()
        events_arg = self.events_path.as_posix()
        approval_arg = self.approval_dir.as_posix()
        cmd = ["meris"]
        if resume and session_id:
            cmd.extend(["session", "resume", session_id, "--event-stream", events_arg])
        else:
            cmd.extend([mode, task, "--event-stream", events_arg])
        if from_plan:
            cmd.append("--from-plan")
        if ratchet_after:
            cmd.append("--ratchet")
        if approve:
            cmd.extend(["--approve", "--approval-channel", approval_arg])

        self.broadcast(
            {
                "type": "runStart",
                "task": task,
                "mode": mode,
                "resume": resume,
                "sessionId": session_id if resume else None,
            }
        )
        self.broadcast({"type": "status", "status": "running"})

        self.proc = subprocess.Popen(
            cmd,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def _stream(pipe, stream_name: str) -> None:
            if not pipe:
                return
            for line in iter(pipe.readline, ""):
                if line:
                    self.broadcast({"type": "terminal", "stream": stream_name, "chunk": line})
            pipe.close()

        if self.proc.stdout:
            threading.Thread(target=_stream, args=(self.proc.stdout, "stdout"), daemon=True).start()
        if self.proc.stderr:
            threading.Thread(target=_stream, args=(self.proc.stderr, "stderr"), daemon=True).start()

        def _wait() -> None:
            code = self.proc.wait() if self.proc else 1
            for ev in self._read_new_events():
                self.broadcast({"type": "event", "event": _enrich_event(self.cwd, ev)})
            with self.lock:
                stderr_snapshot = self.stderr
                self.stderr = ""
                self.proc = None
            status = "done" if code == 0 else "error"
            self.broadcast(
                {
                    "type": "status",
                    "status": status,
                    "code": code,
                    "stderr": stderr_snapshot,
                }
            )
            _finalize_after_run(
                self,
                code=code,
                from_plan=from_plan,
                mark_done=getattr(self, "_plan_mark_done", None),
            )
            self._plan_mark_done = None

        threading.Thread(target=_wait, daemon=True).start()

    def spawn_parallel(self, *, tasks: list[str], mode: str) -> None:
        self.kill()
        self.stderr = ""
        self._prepare_events_file()
        events_arg = self.events_path.as_posix()
        cmd = ["meris", "parallel", *tasks, "--mode", mode, "--event-stream", events_arg]

        self.broadcast({"type": "parallelStart", "tasks": tasks, "mode": mode})
        self.broadcast({"type": "status", "status": "running"})

        self.proc = subprocess.Popen(
            cmd,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def _stream(pipe, stream_name: str) -> None:
            if not pipe:
                return
            for line in iter(pipe.readline, ""):
                if line:
                    self.broadcast({"type": "terminal", "stream": stream_name, "chunk": line})
            pipe.close()

        if self.proc.stdout:
            threading.Thread(target=_stream, args=(self.proc.stdout, "stdout"), daemon=True).start()
        if self.proc.stderr:
            threading.Thread(target=_stream, args=(self.proc.stderr, "stderr"), daemon=True).start()

        def _wait() -> None:
            code = self.proc.wait() if self.proc else 1
            for ev in self._read_new_events():
                self.broadcast({"type": "event", "event": _enrich_event(self.cwd, ev)})
            with self.lock:
                self.proc = None
            status = "done" if code == 0 else "error"
            self.broadcast({"type": "status", "status": status, "code": code})
            self.broadcast({"type": "parallelDone", "code": code, "tasks": tasks})
            self.broadcast({"type": "sessions", "sessions": load_sessions(self.cwd)})

        threading.Thread(target=_wait, daemon=True).start()

    def spawn_cli(self, argv: list[str], *, command_id: str = "", label: str = "") -> bool:
        """Run a one-shot meris subcommand; stream stdout/stderr to terminal panel."""
        if not argv:
            return False
        cmd = ["meris", *argv]
        display = label or " ".join(cmd)
        self.broadcast({"type": "cliRunStart", "commandId": command_id, "cmd": display})

        proc = subprocess.Popen(
            cmd,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def _stream(pipe, stream_name: str) -> None:
            if not pipe:
                return
            for line in iter(pipe.readline, ""):
                if line:
                    self.broadcast({"type": "terminal", "stream": stream_name, "chunk": line})
            pipe.close()

        if proc.stdout:
            threading.Thread(target=_stream, args=(proc.stdout, "stdout"), daemon=True).start()
        if proc.stderr:
            threading.Thread(target=_stream, args=(proc.stderr, "stderr"), daemon=True).start()

        def _wait() -> None:
            code = proc.wait()
            self.broadcast(
                {
                    "type": "cliRunDone",
                    "commandId": command_id,
                    "cmd": display,
                    "code": code,
                    "ok": code == 0,
                }
            )

        threading.Thread(target=_wait, daemon=True).start()
        return True


_RUNTIME: UiRuntime | None = None
_RUNTIME_LOCK = threading.Lock()
_GLOBAL_SSE_LOCK = threading.Lock()
_GLOBAL_SSE_SUBSCRIBERS: list[threading.Condition] = []


def ui_subscribe() -> threading.Condition:
    cond = threading.Condition()
    with _GLOBAL_SSE_LOCK:
        _GLOBAL_SSE_SUBSCRIBERS.append(cond)
    return cond


def ui_unsubscribe(cond: threading.Condition) -> None:
    with _GLOBAL_SSE_LOCK:
        if cond in _GLOBAL_SSE_SUBSCRIBERS:
            _GLOBAL_SSE_SUBSCRIBERS.remove(cond)


def ui_broadcast(msg: dict[str, Any]) -> None:
    payload = json.dumps(msg, ensure_ascii=False)
    with _GLOBAL_SSE_LOCK:
        subs = list(_GLOBAL_SSE_SUBSCRIBERS)
    for cond in subs:
        with cond:
            if not hasattr(cond, "_queue"):
                cond._queue = []  # type: ignore[attr-defined]
            cond._queue.append(payload)  # type: ignore[attr-defined]
            cond.notify()


def get_runtime(cwd: Path) -> UiRuntime:
    global _RUNTIME
    with _RUNTIME_LOCK:
        resolved = cwd.resolve()
        if _RUNTIME is None or _RUNTIME.cwd != resolved:
            if _RUNTIME is not None:
                _RUNTIME.close()
            _RUNTIME = UiRuntime(resolved)
        return _RUNTIME


def switch_runtime(new_path: Path) -> UiRuntime:
    """Replace active UI runtime workspace."""
    global _RUNTIME
    resolved = new_path.resolve()
    with _RUNTIME_LOCK:
        if _RUNTIME is not None:
            _RUNTIME.close()
        _RUNTIME = UiRuntime(resolved)
        return _RUNTIME


def _workspace_info_payload(cwd: Path) -> dict[str, Any]:
    from meris.harness.ui_config import collect_workspace_folders, load_workspace_roots, task_scope_payload
    from meris.ui.harness_data import workspace_label

    folders = collect_workspace_folders(cwd)
    persisted = load_workspace_roots()
    persisted_roots = [{"name": p.name, "path": str(p)} for p in persisted]
    if not persisted_roots:
        persisted_roots = [{"name": cwd.name, "path": str(cwd)}]
    return {
        "cwd": str(cwd),
        "cwdLabel": workspace_label(cwd),
        "folders": folders or [{"name": cwd.name, "path": str(cwd)}],
        "persistedRoots": persisted_roots,
        **task_scope_payload(cwd),
    }


def _broadcast_workspace_switch(rt: UiRuntime, new_path: Path, httpd: Any | None = None) -> UiRuntime:
    """Switch runtime to *new_path* and notify all SSE clients."""
    from meris.harness.ui_config import add_workspace_root

    rt = switch_runtime(new_path)
    add_workspace_root(new_path)
    if httpd is not None:
        httpd.workspace = str(new_path)  # type: ignore[attr-defined]
    payload = _workspace_info_payload(new_path)
    payload["workspaceAction"] = "switch"
    rt.broadcast({"type": "workspaceInfo", **payload})
    rt.broadcast({"type": "sessions", "sessions": load_sessions(new_path)})
    rt.broadcast({"type": "ratchet", **load_ratchet(new_path)})
    from meris.harness.ui_config import plan_payload_for_workspace

    plan_payload = plan_payload_for_workspace(new_path)
    if plan_payload:
        rt.broadcast({"type": "plan", **plan_payload})
    return rt


def _latest_session_row(cwd: Path) -> dict[str, Any] | None:
    rows = load_sessions(cwd)
    return rows[0] if rows else None


def _finalize_after_run(
    rt: UiRuntime,
    *,
    code: int,
    from_plan: bool = False,
    mark_done: list[str] | None = None,
) -> None:
    cwd = rt.cwd
    latest = _latest_session_row(cwd)
    sess_status = str((latest or {}).get("status") or "")
    failed = code != 0 or sess_status in ("dod_failed", "error", "denied")

    if failed:
        from meris.harness.ratchet.post_run import ratchet_post_run

        sid = str((latest or {}).get("id") or "") or None
        ratchet_post_run(cwd, session_id=sid)
        rt.broadcast({"type": "ratchet", **load_ratchet(cwd), "highlight": True})
        rt.broadcast({"type": "ratchetAlert", "reason": sess_status or "error"})
    else:
        rt.broadcast({"type": "ratchet", **load_ratchet(cwd)})
        if from_plan:
            from meris.harness.plan import mark_plan_items_done
            from meris.harness.ui_config import plan_payload_for_workspace

            if mark_done:
                mark_plan_items_done(cwd, ".meris/plan/tasks.md", mark_done)
            payload = plan_payload_for_workspace(cwd)
            if payload:
                rt.broadcast({"type": "plan", **payload})

    rt.broadcast({"type": "sessions", "sessions": load_sessions(cwd)})


def load_sessions(cwd: Path) -> list[dict[str, Any]]:
    sessions_dir = cwd / ".meris" / "sessions"
    if not sessions_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for fp in sessions_dir.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            rows.append(
                {
                    "id": data.get("id") or fp.stem,
                    "task": data.get("task") or "",
                    "mode": data.get("mode") or "run",
                    "status": data.get("status") or "unknown",
                    "turn": data.get("turn") or 0,
                    "updatedAt": data.get("updated_at") or "",
                    "mtime": fp.stat().st_mtime,
                }
            )
        except (json.JSONDecodeError, OSError):
            continue
    rows.sort(key=lambda r: r.get("mtime", 0), reverse=True)
    return rows[:20]


def load_ratchet(cwd: Path) -> dict[str, Any]:
    proposals_dir = cwd / ".meris" / "ratchet" / "proposals"
    proposals: list[dict[str, Any]] = []
    if proposals_dir.is_dir():
        for fp in proposals_dir.glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if data.get("status") != "pending":
                    continue
                proposals.append(
                    {
                        "id": data.get("id"),
                        "lesson": data.get("lesson") or "",
                        "summary": data.get("summary") or "",
                        "target": (data.get("target") or {}).get("path") or "",
                        "mtime": fp.stat().st_mtime,
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
    proposals.sort(key=lambda p: p.get("mtime", 0), reverse=True)
    insights_path = cwd / ".meris" / "ratchet" / "insights" / "pending.jsonl"
    insights_pending = 0
    if insights_path.is_file():
        insights_pending = sum(1 for line in insights_path.read_text(encoding="utf-8").splitlines() if line.strip())
    return {"proposals": proposals[:8], "insightsPending": insights_pending}


def _git_diff(cwd: Path, rel_path: str) -> str:
    if not rel_path:
        return ""
    try:
        out = subprocess.run(
            ["git", "diff", "--unified=3", "--", rel_path],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return (out.stdout or "").strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def _enrich_event(cwd: Path, ev: dict[str, Any]) -> dict[str, Any]:
    if ev.get("kind") != "file_change" or ev.get("diff_preview"):
        return ev
    rel = ev.get("path") or ""
    git_diff = _git_diff(cwd, rel)
    if not git_diff:
        return ev
    return {**ev, "diff_preview": git_diff}


def _write_approval(cwd: Path, request_id: str, approved: bool) -> None:
    d = cwd / ".meris" / "events" / "approval"
    d.mkdir(parents=True, exist_ok=True)
    res = d / "approval-response.json"
    res.write_text(
        json.dumps({"request_id": request_id, "approved": approved}, ensure_ascii=False),
        encoding="utf-8",
    )


def _run_ratchet(cwd: Path, subcmd: str, proposal_id: str = "") -> dict[str, Any]:
    cmd = ["meris", "ratchet", subcmd]
    if proposal_id:
        cmd.append(proposal_id)
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)
        return {"ok": proc.returncode == 0, "stderr": (proc.stderr or "")[-300:]}
    except (subprocess.SubprocessError, OSError) as e:
        return {"ok": False, "stderr": str(e)}


def _list_workspace_files(cwd: Path, query: str = "") -> list[str]:
    skip = {".git", "node_modules", ".meris", "__pycache__", ".venv"}
    out: list[str] = []
    q = query.lower()
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in skip]
        for name in files:
            rel = Path(root, name).relative_to(cwd).as_posix()
            if q and q not in rel.lower():
                continue
            out.append(rel)
            if len(out) >= 80:
                return out
    return sorted(out)


def _read_workspace_file(cwd: Path, rel: str) -> dict[str, Any]:
    p = (cwd / rel).resolve()
    if not str(p).startswith(str(cwd.resolve())):
        raise ValueError("path escapes workspace")
    return {"path": rel, "content": p.read_text(encoding="utf-8", errors="replace")[:12000]}


def _apply_hunk(cwd: Path, rel: str, patch: str) -> None:
    tmp = cwd / ".meris" / "tmp" / "hunk.patch"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    body = patch if "---" in patch else f"--- a/{rel}\n+++ b/{rel}\n{patch}"
    tmp.write_text(body, encoding="utf-8")
    subprocess.run(["git", "apply", "--unsafe-paths", str(tmp)], cwd=cwd, check=True, capture_output=True)


def _serve_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
    if not path.is_file():
        handler.send_error(HTTPStatus.NOT_FOUND)
        return
    data = path.read_bytes()
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class MerisUiHandler(BaseHTTPRequestHandler):
    server_version = "MerisUI/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def runtime(self) -> UiRuntime:
        global _RUNTIME
        with _RUNTIME_LOCK:
            if _RUNTIME is not None:
                return _RUNTIME
        return get_runtime(Path(self.server.workspace))  # type: ignore[attr-defined]

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path

        if route == "/":
            return _serve_file(self, _UI_STATIC / "index.html")
        if route.startswith("/media/"):
            rel = route.removeprefix("/media/")
            target = (_EXT_MEDIA / rel).resolve()
            if not str(target).startswith(str(_EXT_MEDIA.resolve())):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            return _serve_file(self, target)
        if route == "/api/events":
            return self._handle_sse()
        if route == "/api/health":
            return self._send_json({"ok": True, "cwd": str(self.runtime.cwd)})
        if route == "/api/workspace":
            return self._send_json(_workspace_info_payload(self.runtime.cwd))
        if route == "/api/sessions":
            return self._send_json({"sessions": load_sessions(self.runtime.cwd)})
        if route == "/api/workspace-file":
            from urllib.parse import parse_qs

            qs = parse_qs(parsed.query)
            rel = (qs.get("path") or [""])[0]
            root_raw = (qs.get("root") or [""])[0]
            root_cwd = Path(root_raw).resolve() if root_raw else self.runtime.cwd
            try:
                p = (root_cwd / rel).resolve()
                if not str(p).startswith(str(root_cwd.resolve())):
                    raise ValueError("path escapes workspace")
                if not p.is_file():
                    raise FileNotFoundError(rel)
                return _serve_file(self, p)
            except (OSError, ValueError):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        if route == "/api/dir":
            from meris.ui.harness_data import list_dir_entries
            from urllib.parse import parse_qs

            qs = parse_qs(parsed.query)
            rel = (qs.get("path") or [""])[0]
            root_raw = (qs.get("root") or [""])[0]
            root_cwd = Path(root_raw).resolve() if root_raw else self.runtime.cwd
            try:
                entries = list_dir_entries(root_cwd, rel)
            except (ValueError, OSError):
                entries = []
            return self._send_json({"dir": rel, "root": str(root_cwd), "entries": entries})
        if route == "/api/browse":
            from meris.ui.harness_data import browse_directories
            from urllib.parse import parse_qs

            qs = parse_qs(parsed.query)
            abs_path = (qs.get("path") or [""])[0]
            return self._send_json(browse_directories(abs_path))
        if route == "/api/skills":
            from meris.ui.harness_data import list_skills_for_ui, skill_prefs_for_ui

            return self._send_json(
                {
                    "skills": list_skills_for_ui(self.runtime.cwd),
                    "prefs": skill_prefs_for_ui(self.runtime.cwd),
                }
            )
        if route == "/api/mcp":
            from meris.ui.harness_data import list_mcp_for_ui

            info = list_mcp_for_ui(self.runtime.cwd, probe=True)
            try:
                proc = subprocess.run(
                    ["meris", "mcp", "list"],
                    cwd=self.runtime.cwd,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
                info["tools"] = [
                    ln.strip()
                    for ln in (proc.stdout or "").splitlines()
                    if ln.strip() and not ln.strip().startswith("(")
                ][:24]
            except (subprocess.SubprocessError, OSError):
                info["tools"] = []
            return self._send_json(info)
        if route == "/api/commands":
            from meris.ui.harness_data import list_cli_commands_for_ui

            return self._send_json(list_cli_commands_for_ui())
        if route == "/api/docs":
            from meris.ui.harness_data import list_harness_docs_for_ui

            return self._send_json({"docs": list_harness_docs_for_ui()})
        if route == "/api/doc":
            from meris.ui.harness_data import read_harness_doc_for_ui
            from urllib.parse import parse_qs

            qs = parse_qs(parsed.query)
            doc_id = (qs.get("id") or [""])[0]
            payload = read_harness_doc_for_ui(doc_id)
            if not payload:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            return self._send_json(payload)
        if route == "/api/rules":
            from meris.ui.harness_data import list_rules_for_ui

            return self._send_json({"rules": list_rules_for_ui(self.runtime.cwd)})
        if route == "/api/models":
            from meris.ui.harness_data import list_models_for_ui

            return self._send_json(list_models_for_ui(self.runtime.cwd))

        self.send_error(HTTPStatus.NOT_FOUND)

    def _handle_sse(self) -> None:
        cond = ui_subscribe()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            self.runtime.broadcast({"type": "sessions", "sessions": load_sessions(self.runtime.cwd)})
            self.runtime.broadcast({"type": "ratchet", **load_ratchet(self.runtime.cwd)})
            from meris.harness.ui_config import plan_payload_for_workspace

            plan_payload = plan_payload_for_workspace(self.runtime.cwd)
            if plan_payload:
                self.runtime.broadcast({"type": "plan", **plan_payload})

            while True:
                with cond:
                    queue = getattr(cond, "_queue", [])
                    if not queue:
                        cond.wait(timeout=15)
                    batch = list(getattr(cond, "_queue", []))
                    cond._queue = []  # type: ignore[attr-defined]
                for payload in batch:
                    line = f"data: {payload}\n\n".encode("utf-8")
                    self.wfile.write(line)
                    self.wfile.flush()
                if not batch:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            ui_unsubscribe(cond)

    def _handle_skill_set_source(self) -> None:
        from meris.harness.ui_config import set_skill_import_source
        from meris.ui.harness_data import list_skills_for_ui, skill_prefs_for_ui

        msg = self._read_json()
        path = str(msg.get("path") or "").strip()
        if not path:
            return self._send_json({"ok": False, "error": "path required"}, status=400)
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_dir():
            return self._send_json({"ok": False, "error": "not a directory"}, status=400)
        set_skill_import_source(self.runtime.cwd, str(resolved))
        prefs = skill_prefs_for_ui(self.runtime.cwd)
        payload = {
            "ok": True,
            "path": str(resolved),
            "prefs": prefs,
            "skills": list_skills_for_ui(self.runtime.cwd),
        }
        ui_broadcast({"type": "skillImportSource", **payload})
        return self._send_json(payload)

    def _handle_skill_import(self) -> None:
        from meris.harness.ui_config import import_skills_from_dir, resolve_skill_import_source
        from meris.ui.harness_data import list_skills_for_ui, skill_prefs_for_ui

        msg = self._read_json()
        explicit = str(msg.get("path") or "").strip() or None
        src = resolve_skill_import_source(self.runtime.cwd, explicit)
        if not src:
            payload = {
                "ok": False,
                "detail": "请先选择本地技能目录",
                "prefs": skill_prefs_for_ui(self.runtime.cwd),
                "skills": list_skills_for_ui(self.runtime.cwd),
            }
            ui_broadcast({"type": "importResult", "ok": False, "kind": "skills", **payload})
            return self._send_json(payload, status=400)
        count = import_skills_from_dir(self.runtime.cwd, src)
        detail = (
            f"已从 {src} 导入 {count} 个技能"
            if count > 0
            else f"目录为空或无可识别技能：{src}"
        )
        payload = {
            "ok": count > 0,
            "count": count,
            "detail": detail,
            "sourcePath": str(src),
            "prefs": skill_prefs_for_ui(self.runtime.cwd),
            "skills": list_skills_for_ui(self.runtime.cwd),
        }
        ui_broadcast({"type": "skillsList", "skills": payload["skills"], "prefs": payload["prefs"]})
        ui_broadcast(
            {
                "type": "importResult",
                "ok": payload["ok"],
                "kind": "skills",
                "detail": detail,
                "sourcePath": str(src),
            }
        )
        return self._send_json(payload)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/task-scope":
            body = self._read_json()
            raw_paths = body.get("paths") if isinstance(body, dict) else None
            paths: list[Path] = []
            if isinstance(raw_paths, list):
                for item in raw_paths:
                    try:
                        p = Path(str(item)).expanduser().resolve()
                    except OSError:
                        continue
                    if p.is_dir():
                        paths.append(p)
            from meris.harness.ui_config import set_task_scope

            selected = set_task_scope(paths, cwd=self.runtime.cwd)
            payload = _workspace_info_payload(self.runtime.cwd)
            self.runtime.broadcast({"type": "workspaceInfo", **payload})
            return self._send_json(
                {
                    "ok": True,
                    "paths": [str(p) for p in selected],
                    "workspace": payload,
                }
            )
        if parsed.path == "/api/skills/set-source":
            return self._handle_skill_set_source()
        if parsed.path == "/api/skills/import":
            return self._handle_skill_import()
        if parsed.path != "/api/cmd":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        msg = self._read_json()
        mtype = msg.get("type")
        rt = self.runtime
        cwd = rt.cwd

        if mtype == "submit":
            rt.spawn_run(
                task=str(msg.get("task") or ""),
                mode=str(msg.get("mode") or "run"),
                approve=bool(msg.get("approve")),
                resume=False,
                session_id="",
            )
        elif mtype == "planRun":
            from meris.harness.ui_config import pick_plan_execute_root

            exec_root = pick_plan_execute_root(cwd)
            mark_done = [str(t) for t in (msg.get("markDone") or []) if str(t).strip()]
            if exec_root.resolve() != cwd.resolve():
                rt = _broadcast_workspace_switch(rt, exec_root, self)
            rt._plan_mark_done = mark_done or None
            rt.spawn_run(
                task=str(msg.get("task") or "implement the plan"),
                mode="run",
                approve=bool(msg.get("approve")),
                resume=False,
                session_id="",
                from_plan=True,
                ratchet_after=True,
            )
        elif mtype == "resumeSession":
            rt.spawn_run(
                task="",
                mode="run",
                approve=bool(msg.get("approve")),
                resume=True,
                session_id=str(msg.get("sessionId") or ""),
            )
        elif mtype == "stop":
            rt.kill()
            rt.broadcast({"type": "status", "status": "cancelled"})
        elif mtype == "refreshSessions":
            rt.broadcast({"type": "sessions", "sessions": load_sessions(cwd)})
        elif mtype == "refreshRatchet":
            rt.broadcast({"type": "ratchet", **load_ratchet(cwd)})
        elif mtype == "ratchetScan":
            result = _run_ratchet(cwd, "scan")
            rt.broadcast(
                {
                    "type": "ratchetResult",
                    "action": "scan",
                    "ok": result["ok"],
                    "detail": result.get("stderr") or "",
                }
            )
            rt.broadcast({"type": "ratchet", **load_ratchet(cwd)})
        elif mtype == "ratchetApply":
            pid = str(msg.get("proposalId") or "")
            result = _run_ratchet(cwd, "apply", pid)
            rt.broadcast(
                {
                    "type": "ratchetResult",
                    "action": "apply",
                    "proposalId": pid,
                    "ok": result["ok"],
                    "detail": result.get("stderr") or "",
                }
            )
            rt.broadcast({"type": "ratchet", **load_ratchet(cwd)})
        elif mtype == "ratchetReject":
            pid = str(msg.get("proposalId") or "")
            result = _run_ratchet(cwd, "reject", pid)
            rt.broadcast(
                {
                    "type": "ratchetResult",
                    "action": "reject",
                    "proposalId": pid,
                    "ok": result["ok"],
                    "detail": result.get("stderr") or "",
                }
            )
            rt.broadcast({"type": "ratchet", **load_ratchet(cwd)})
        elif mtype == "approvalResponse":
            _write_approval(cwd, str(msg.get("requestId") or ""), bool(msg.get("approved")))
        elif mtype == "getWorkspace":
            rt.broadcast({"type": "workspaceInfo", **_workspace_info_payload(rt.cwd)})
        elif mtype == "pickFolder":
            from meris.ui.folder_picker import pick_native_folder

            intent = str(msg.get("intent") or "add")
            handler = self
            start_cwd = rt.cwd

            def _pick_async() -> None:
                active_rt = get_runtime(start_cwd)
                try:
                    active_rt.broadcast({"type": "folderPicking", "active": True, "intent": intent})
                    picked = pick_native_folder(start_cwd)
                except Exception as exc:
                    active_rt.broadcast({"type": "folderPicking", "active": False, "intent": intent})
                    active_rt.broadcast(
                        {
                            "type": "workspacePickError",
                            "error": f"文件夹选择器失败: {exc}",
                        }
                    )
                    return
                if not picked:
                    active_rt.broadcast(
                        {"type": "folderPicking", "active": False, "cancelled": True, "intent": intent}
                    )
                    active_rt.broadcast(
                        {
                            "type": "workspacePickError",
                            "error": "未选择文件夹。若未看到系统对话框，请在弹窗中手动输入路径。",
                        }
                    )
                    return
                new_path = Path(picked).resolve()
                if not new_path.is_dir():
                    active_rt.broadcast({"type": "folderPicking", "active": False, "intent": intent})
                    active_rt.broadcast(
                        {"type": "workspacePickError", "error": "所选路径不是文件夹"}
                    )
                    return
                if intent == "switch":
                    _broadcast_workspace_switch(active_rt, new_path, handler.server)
                elif intent == "importSkills":
                    from meris.harness.ui_config import set_skill_import_source
                    from meris.ui.harness_data import list_skills_for_ui, skill_prefs_for_ui

                    set_skill_import_source(active_rt.cwd, str(new_path))
                    active_rt.broadcast(
                        {
                            "type": "skillImportSource",
                            "path": str(new_path),
                            "prefs": skill_prefs_for_ui(active_rt.cwd),
                            "skills": list_skills_for_ui(active_rt.cwd),
                        }
                    )
                else:
                    from meris.harness.ui_config import add_workspace_root

                    _, created = add_workspace_root(new_path)
                    payload = _workspace_info_payload(active_rt.cwd)
                    payload["workspaceAction"] = "add"
                    payload["addedPath"] = str(new_path)
                    payload["alreadyExists"] = not created
                    active_rt.broadcast({"type": "workspaceInfo", **payload})
                active_rt.broadcast({"type": "folderPicking", "active": False, "intent": intent})

            threading.Thread(target=_pick_async, daemon=True).start()
            return self._send_json({"ok": True, "picking": True, "intent": intent})
        elif mtype == "setTaskScope":
            raw_paths = msg.get("paths")
            paths: list[Path] = []
            if isinstance(raw_paths, list):
                for item in raw_paths:
                    try:
                        p = Path(str(item)).expanduser().resolve()
                    except OSError:
                        continue
                    if p.is_dir():
                        paths.append(p)
            from meris.harness.ui_config import set_task_scope

            selected = set_task_scope(paths, cwd=rt.cwd)
            payload = _workspace_info_payload(rt.cwd)
            rt.broadcast({"type": "workspaceInfo", **payload})
            return self._send_json(
                {
                    "ok": True,
                    "paths": [str(p) for p in selected],
                    "workspace": payload,
                    "message": "已更新本次任务范围",
                }
            )
        elif mtype == "setWorkspace":
            new_path = Path(str(msg.get("path") or "")).resolve()
            if not new_path.is_dir():
                return self._send_json({"ok": False, "error": "not a directory"}, status=400)
            _broadcast_workspace_switch(rt, new_path, self.server)
            payload = _workspace_info_payload(new_path)
            return self._send_json({"ok": True, "workspace": payload, "message": f"已切换到 {new_path.name}"})
        elif mtype == "addWorkspaceRoot":
            new_path = Path(str(msg.get("path") or "")).resolve()
            if not new_path.is_dir():
                return self._send_json({"ok": False, "error": "not a directory"}, status=400)
            from meris.harness.ui_config import add_workspace_root

            try:
                _, created = add_workspace_root(new_path)
            except ValueError as exc:
                err = str(exc)
                if "skill" in err.lower():
                    err = "Skill 目录不能作为项目根 — 请在设置 → 技能 管理"
                return self._send_json({"ok": False, "error": err}, status=400)
            payload = _workspace_info_payload(rt.cwd)
            payload["workspaceAction"] = "add"
            payload["addedPath"] = str(new_path)
            payload["alreadyExists"] = not created
            rt.broadcast({"type": "workspaceInfo", **payload})
            message = (
                f"已在项目列表：{new_path}"
                if not created
                else f"已添加项目：{new_path.name}"
            )
            return self._send_json(
                {
                    "ok": True,
                    "workspace": payload,
                    "message": message,
                    "alreadyExists": not created,
                }
            )
        elif mtype == "removeWorkspaceRoot":
            rem = Path(str(msg.get("path") or "")).resolve()
            from meris.harness.ui_config import load_workspace_roots, prune_task_scope_from_paths, remove_workspace_root

            remove_workspace_root(rem)
            prune_task_scope_from_paths([rem], cwd=rt.cwd)
            if rt.cwd.resolve() == rem:
                remaining = load_workspace_roots()
                if remaining:
                    rt = _broadcast_workspace_switch(rt, remaining[0], self.server)
                    payload = _workspace_info_payload(rt.cwd)
                else:
                    payload = _workspace_info_payload(rt.cwd)
                    payload["workspaceAction"] = "update"
                    rt.broadcast({"type": "workspaceInfo", **payload})
            else:
                payload = _workspace_info_payload(rt.cwd)
                payload["workspaceAction"] = "update"
                rt.broadcast({"type": "workspaceInfo", **payload})
            return self._send_json({"ok": True, "workspace": payload, "message": "已移除根目录"})
        elif mtype == "openMerisRoot":
            from meris.harness.ui_config import find_meris_roots

            roots = find_meris_roots([rt.cwd])
            target = roots[0] if roots else None
            if target and target.resolve() != rt.cwd.resolve():
                rt = switch_runtime(target)
                self.server.workspace = str(target)  # type: ignore[attr-defined]
            rt.broadcast({"type": "workspaceInfo", **_workspace_info_payload(rt.cwd)})
            rt.broadcast({"type": "sessions", "sessions": load_sessions(rt.cwd)})
        elif mtype == "importCursorMcp":
            from meris.harness.ui_config import load_cursor_mcp_json, save_ui_mcp_servers
            from meris.ui.harness_data import list_mcp_for_ui

            imported = load_cursor_mcp_json(rt.cwd)
            if not imported:
                rt.broadcast({"type": "mcpImportError", "error": "未找到 .cursor/mcp.json"})
            else:
                save_ui_mcp_servers(rt.cwd, imported)
                info = list_mcp_for_ui(rt.cwd)
                rt.broadcast({"type": "mcpInfo", **info})
                rt.broadcast(
                    {
                        "type": "importResult",
                        "ok": True,
                        "kind": "mcp",
                        "detail": "已从 .cursor/mcp.json 导入 MCP",
                    }
                )
        elif mtype == "saveMcpServers":
            from meris.harness.ui_config import mcp_servers_dict_from_ui_items, save_ui_mcp_servers
            from meris.ui.harness_data import list_mcp_for_ui

            items = msg.get("servers") if isinstance(msg.get("servers"), list) else []
            save_ui_mcp_servers(rt.cwd, mcp_servers_dict_from_ui_items(items))
            info = list_mcp_for_ui(rt.cwd)
            rt.broadcast({"type": "mcpInfo", **info})
        elif mtype == "migrateMcpToUi":
            from meris.harness.ui_config import migrate_mcp_to_ui
            from meris.ui.harness_data import list_mcp_for_ui

            ok = migrate_mcp_to_ui(rt.cwd)
            info = list_mcp_for_ui(rt.cwd)
            rt.broadcast({"type": "mcpInfo", **info})
            rt.broadcast(
                {
                    "type": "importResult",
                    "ok": ok,
                    "kind": "mcp",
                    "detail": (
                        "已从 settings.yaml 迁移到 UI 配置"
                        if ok
                        else "无可迁移的 MCP 或已存在 UI 配置"
                    ),
                }
            )
        elif mtype == "importMcpFromPath":
            from meris.harness.ui_config import import_mcp_from_path
            from meris.ui.harness_data import list_mcp_for_ui

            file_path = Path(str(msg.get("path") or ""))
            ok = import_mcp_from_path(rt.cwd, file_path)
            info = list_mcp_for_ui(rt.cwd)
            rt.broadcast({"type": "mcpInfo", **info})
            rt.broadcast(
                {
                    "type": "importResult",
                    "ok": ok,
                    "kind": "mcp",
                    "detail": (
                        f"已从 {file_path} 导入 MCP"
                        if ok
                        else f"无法从 {file_path} 导入 MCP"
                    ),
                }
            )
        elif mtype == "importRulesFromPath":
            from meris.harness.ui_config import import_rules_from_dir
            from meris.ui.harness_data import list_rules_for_ui

            dir_path = Path(str(msg.get("path") or ""))
            count = import_rules_from_dir(rt.cwd, dir_path)
            if count > 0:
                rt.broadcast({"type": "rulesList", "rules": list_rules_for_ui(rt.cwd)})
            rt.broadcast(
                {
                    "type": "importResult",
                    "ok": count > 0,
                    "kind": "rules",
                    "detail": (
                        f"已从 {dir_path} 导入 {count} 条规则"
                        if count > 0
                        else f"目录为空或无可导入文件：{dir_path}"
                    ),
                }
            )
        elif mtype == "saveSkill":
            from meris.harness.ui_config import save_skill
            from meris.ui.harness_data import list_skills_for_ui, read_skill_for_ui, skill_prefs_for_ui

            try:
                name = str(msg.get("name") or "")
                content = str(msg.get("content") or "")
                saved = save_skill(rt.cwd, name, content)
                skill_name = saved.stem
                rt.broadcast(
                    {
                        "type": "skillsList",
                        "skills": list_skills_for_ui(rt.cwd),
                        "prefs": skill_prefs_for_ui(rt.cwd),
                    }
                )
                item = read_skill_for_ui(rt.cwd, skill_name)
                if item:
                    rt.broadcast({"type": "contextItem", "item": item})
            except (OSError, ValueError):
                pass
        elif mtype == "saveGlobalSkill":
            from meris.harness.ui_config import save_global_skill
            from meris.ui.harness_data import list_skills_for_ui, read_skill_for_ui, skill_prefs_for_ui

            try:
                name = str(msg.get("name") or "")
                content = str(msg.get("content") or "")
                saved = save_global_skill(name, content)
                skill_name = saved.stem
                rt.broadcast(
                    {
                        "type": "skillsList",
                        "skills": list_skills_for_ui(rt.cwd),
                        "prefs": skill_prefs_for_ui(rt.cwd),
                    }
                )
                if msg.get("forEditor"):
                    item = read_skill_for_ui(rt.cwd, skill_name)
                    if item:
                        rt.broadcast(
                            {
                                "type": "skillContent",
                                "name": skill_name,
                                "content": item.get("content") or "",
                                "skills": list_skills_for_ui(rt.cwd),
                                "prefs": skill_prefs_for_ui(rt.cwd),
                            }
                        )
            except (OSError, ValueError):
                pass
        elif mtype == "listDir":
            from meris.ui.harness_data import list_dir_entries

            rel = str(msg.get("dir") or "")
            root_raw = str(msg.get("root") or rt.cwd)
            root_cwd = Path(root_raw).resolve()
            try:
                entries = list_dir_entries(root_cwd, rel)
            except (ValueError, OSError):
                entries = []
            rt.broadcast(
                {
                    "type": "dirListing",
                    "dir": rel,
                    "root": str(root_cwd),
                    "entries": entries,
                }
            )
        elif mtype == "listSkills":
            from meris.ui.harness_data import list_skills_for_ui, skill_prefs_for_ui

            rt.broadcast(
                {
                    "type": "skillsList",
                    "skills": list_skills_for_ui(rt.cwd),
                    "prefs": skill_prefs_for_ui(rt.cwd),
                }
            )
        elif mtype == "toggleSkillEnabled":
            from meris.harness.ui_config import set_skill_enabled
            from meris.ui.harness_data import list_skills_for_ui, skill_prefs_for_ui

            name = str(msg.get("name") or "")
            enabled = bool(msg.get("enabled"))
            try:
                set_skill_enabled(rt.cwd, name, enabled)
            except ValueError:
                pass
            rt.broadcast(
                {
                    "type": "skillsList",
                    "skills": list_skills_for_ui(rt.cwd),
                    "prefs": skill_prefs_for_ui(rt.cwd),
                }
            )
        elif mtype == "importSkills":
            from meris.harness.ui_config import import_skills_from_dir, resolve_skill_import_source
            from meris.ui.harness_data import list_skills_for_ui, skill_prefs_for_ui

            explicit = str(msg.get("path") or "").strip() or None
            src = resolve_skill_import_source(rt.cwd, explicit)
            if not src:
                rt.broadcast(
                    {
                        "type": "importResult",
                        "ok": False,
                        "kind": "skills",
                        "detail": "请先选择本地技能目录",
                    }
                )
            else:
                count = import_skills_from_dir(rt.cwd, src)
                rt.broadcast(
                    {
                        "type": "skillsList",
                        "skills": list_skills_for_ui(rt.cwd),
                        "prefs": skill_prefs_for_ui(rt.cwd),
                    }
                )
                rt.broadcast(
                    {
                        "type": "importResult",
                        "ok": count > 0,
                        "kind": "skills",
                        "detail": (
                            f"已从 {src} 导入 {count} 个技能"
                            if count > 0
                            else f"目录为空或无可识别技能：{src}"
                        ),
                        "sourcePath": str(src),
                    }
                )
        elif mtype == "importCursorSkills":
            from meris.harness.ui_config import import_skills_from_dir
            from meris.ui.harness_data import list_skills_for_ui, skill_prefs_for_ui

            src = rt.cwd / ".cursor" / "skills"
            if not src.is_dir():
                rt.broadcast(
                    {
                        "type": "importResult",
                        "ok": False,
                        "kind": "skills",
                        "detail": "未找到 .cursor/skills/ 或可导入文件",
                    }
                )
            else:
                count = import_skills_from_dir(rt.cwd, src)
                rt.broadcast(
                    {
                        "type": "skillsList",
                        "skills": list_skills_for_ui(rt.cwd),
                        "prefs": skill_prefs_for_ui(rt.cwd),
                    }
                )
                rt.broadcast(
                    {
                        "type": "importResult",
                        "ok": count > 0,
                        "kind": "skills",
                        "detail": (
                            f"已从 {src} 导入 {count} 个技能"
                            if count > 0
                            else f"目录为空或无可识别技能：{src}"
                        ),
                        "sourcePath": str(src),
                    }
                )
        elif mtype == "installBundledSkill":
            from meris.harness.ui_config import install_bundled_skill
            from meris.ui.harness_data import list_skills_for_ui, read_skill_for_ui, skill_prefs_for_ui

            name = str(msg.get("name") or "")
            try:
                install_bundled_skill(rt.cwd, name)
            except ValueError:
                pass
            rt.broadcast(
                {
                    "type": "skillsList",
                    "skills": list_skills_for_ui(rt.cwd),
                    "prefs": skill_prefs_for_ui(rt.cwd),
                }
            )
            item = read_skill_for_ui(rt.cwd, name)
            if item and msg.get("forEditor"):
                rt.broadcast(
                    {
                        "type": "skillContent",
                        "name": name,
                        "content": item.get("content") or "",
                        "skills": list_skills_for_ui(rt.cwd),
                        "prefs": skill_prefs_for_ui(rt.cwd),
                    }
                )
        elif mtype == "installBundledToGlobal":
            from meris.harness.ui_config import install_bundled_to_global
            from meris.ui.harness_data import list_skills_for_ui, read_skill_for_ui, skill_prefs_for_ui

            name = str(msg.get("name") or "")
            try:
                install_bundled_to_global(name)
            except ValueError:
                pass
            rt.broadcast(
                {
                    "type": "skillsList",
                    "skills": list_skills_for_ui(rt.cwd),
                    "prefs": skill_prefs_for_ui(rt.cwd),
                }
            )
            item = read_skill_for_ui(rt.cwd, name)
            if item and msg.get("forEditor"):
                rt.broadcast(
                    {
                        "type": "skillContent",
                        "name": name,
                        "content": item.get("content") or "",
                        "skills": list_skills_for_ui(rt.cwd),
                        "prefs": skill_prefs_for_ui(rt.cwd),
                    }
                )
        elif mtype == "saveSkillPrefs":
            from meris.harness.ui_config import load_skill_prefs, save_skill_prefs, set_skill_import_source
            from meris.ui.harness_data import list_skills_for_ui, skill_prefs_for_ui

            if "importSourcePath" in msg:
                set_skill_import_source(rt.cwd, str(msg.get("importSourcePath") or ""))
            else:
                prefs = load_skill_prefs(rt.cwd)
                save_skill_prefs(rt.cwd, prefs)
            rt.broadcast(
                {
                    "type": "skillsList",
                    "skills": list_skills_for_ui(rt.cwd),
                    "prefs": skill_prefs_for_ui(rt.cwd),
                }
            )
        elif mtype == "readSkill":
            from meris.ui.harness_data import list_skills_for_ui, read_skill_for_ui, skill_prefs_for_ui

            name = str(msg.get("name") or "")
            item = read_skill_for_ui(rt.cwd, name)
            if item:
                if msg.get("forEditor"):
                    rt.broadcast(
                        {
                            "type": "skillContent",
                            "name": name,
                            "content": item.get("content") or "",
                            "skills": list_skills_for_ui(rt.cwd),
                            "prefs": skill_prefs_for_ui(rt.cwd),
                        }
                    )
                else:
                    rt.broadcast({"type": "contextItem", "item": item})
        elif mtype == "listRules":
            from meris.ui.harness_data import list_rules_for_ui

            rt.broadcast({"type": "rulesList", "rules": list_rules_for_ui(rt.cwd)})
        elif mtype == "readRule":
            from meris.ui.harness_data import read_rule_for_ui

            name = str(msg.get("name") or "")
            item = read_rule_for_ui(rt.cwd, name)
            if item:
                rt.broadcast(
                    {
                        "type": "ruleContent",
                        "name": item.get("name") or name,
                        "content": item.get("content") or "",
                    }
                )
        elif mtype == "saveRule":
            from meris.harness.ui_config import save_rule
            from meris.ui.harness_data import list_rules_for_ui

            try:
                name = str(msg.get("name") or "")
                content = str(msg.get("content") or "")
                save_rule(rt.cwd, name, content)
                rt.broadcast({"type": "rulesList", "rules": list_rules_for_ui(rt.cwd)})
            except (OSError, ValueError):
                pass
        elif mtype == "getModels":
            from meris.ui.harness_data import list_models_for_ui

            rt.broadcast({"type": "modelsInfo", **list_models_for_ui(rt.cwd)})
        elif mtype == "importCursorRules":
            from meris.harness.ui_config import import_cursor_rules
            from meris.ui.harness_data import list_rules_for_ui

            count = import_cursor_rules(rt.cwd)
            if count <= 0:
                rt.broadcast(
                    {
                        "type": "importResult",
                        "ok": False,
                        "kind": "rules",
                        "detail": "未找到 .cursor/rules/ 或可导入文件",
                    }
                )
            else:
                rt.broadcast({"type": "rulesList", "rules": list_rules_for_ui(rt.cwd)})
                rt.broadcast(
                    {
                        "type": "importResult",
                        "ok": True,
                        "kind": "rules",
                        "detail": f"已导入 {count} 条规则",
                    }
                )
        elif mtype == "listMcp":
            from meris.ui.harness_data import list_mcp_for_ui

            info = list_mcp_for_ui(rt.cwd, probe=True)
            try:
                proc = subprocess.run(
                    ["meris", "mcp", "list"],
                    cwd=rt.cwd,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
                info["tools"] = [
                    ln.strip()
                    for ln in (proc.stdout or "").splitlines()
                    if ln.strip() and not ln.strip().startswith("(")
                ][:24]
            except (subprocess.SubprocessError, OSError):
                info["tools"] = []
            rt.broadcast({"type": "mcpInfo", **info})
        elif mtype == "listCommands":
            from meris.ui.harness_data import list_cli_commands_for_ui

            rt.broadcast({"type": "commandsList", **list_cli_commands_for_ui()})
        elif mtype == "listDocs":
            from meris.ui.harness_data import list_harness_docs_for_ui

            rt.broadcast({"type": "docsList", "docs": list_harness_docs_for_ui()})
        elif mtype == "readDoc":
            from meris.ui.harness_data import read_harness_doc_for_ui

            doc = read_harness_doc_for_ui(str(msg.get("id") or ""))
            if doc:
                rt.broadcast({"type": "docContent", **doc})
        elif mtype == "listContextFiles":
            rt.broadcast({"type": "contextFiles", "files": _list_workspace_files(cwd, str(msg.get("query") or ""))})
        elif mtype == "readContextFile":
            try:
                root_cwd = Path(str(msg.get("root") or rt.cwd)).resolve()
                item = _read_workspace_file(root_cwd, str(msg.get("path") or ""))
                rt.broadcast({"type": "contextItem", "item": item})
            except (OSError, ValueError):
                pass
        elif mtype == "saveContextImage":
            from meris.ui.harness_data import save_context_image_for_ui

            try:
                item = save_context_image_for_ui(
                    rt.cwd,
                    data_url=str(msg.get("dataUrl") or ""),
                    filename=str(msg.get("filename") or ""),
                )
                rt.broadcast({"type": "contextItem", "item": item})
            except (OSError, ValueError) as exc:
                rt.broadcast({"type": "contextImageError", "error": str(exc)})
        elif mtype == "applyHunk":
            try:
                _apply_hunk(cwd, str(msg.get("path") or ""), str(msg.get("patch") or ""))
            except (subprocess.CalledProcessError, OSError):
                pass
        elif mtype == "loadPreview":
            rel = str(msg.get("path") or "")
            try:
                html = (cwd / rel).read_text(encoding="utf-8", errors="replace")
                rt.broadcast({"type": "preview", "path": rel, "html": html})
            except OSError:
                pass
        elif mtype == "clearPlan":
            from meris.harness.paths import harness_root

            rel = str(msg.get("path") or ".meris/plan/tasks.md")
            plan_file = (cwd / rel).resolve()
            harness_plan = (harness_root(cwd) / "plan" / "tasks.md").resolve()
            for candidate in {plan_file, harness_plan}:
                try:
                    if candidate.is_file() and str(candidate).startswith(str(cwd.resolve())):
                        candidate.unlink()
                except OSError:
                    pass
            rt.broadcast({"type": "planCleared"})
            rt.broadcast({"type": "plan", "path": "", "items": []})
            return self._send_json({"ok": True})
        elif mtype == "savePlan":
            if msg.get("path") and msg.get("items"):
                from meris.harness.plan import parse_plan_checkboxes, sync_plan_items

                saved = sync_plan_items(cwd, str(msg["path"]), msg["items"])
                try:
                    rel = str(saved.relative_to(cwd))
                except ValueError:
                    rel = str(saved)
                rt.broadcast(
                    {
                        "type": "planSaved",
                        "path": rel,
                        "items": parse_plan_checkboxes(saved.read_text(encoding="utf-8")),
                    }
                )
        elif mtype == "parallelRun":
            tasks = [str(t) for t in (msg.get("tasks") or []) if t]
            if tasks:
                rt.spawn_parallel(tasks=tasks, mode=str(msg.get("mode") or "ask"))
        elif mtype == "runCliCommand":
            from meris.ui.cli_runner import resolve_runnable_cli

            cmd_id = str(msg.get("id") or "")
            argv = resolve_runnable_cli(cmd_id)
            if not argv:
                rt.broadcast(
                    {
                        "type": "cliRunDone",
                        "commandId": cmd_id,
                        "cmd": cmd_id,
                        "code": 1,
                        "ok": False,
                        "error": "command not runnable from UI",
                    }
                )
            else:
                rt.spawn_cli(argv, command_id=cmd_id, label="meris " + " ".join(argv))

        self._send_json({"ok": True})


def serve_ui(*, cwd: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    from meris.harness.ui_config import add_workspace_root, prune_workspace_roots

    resolved = cwd.resolve()
    kept, removed = prune_workspace_roots()
    if removed:
        print(f"Meris UI: pruned {removed} stale workspace root(s)", flush=True)
    add_workspace_root(resolved)
    get_runtime(resolved)
    httpd = ThreadingHTTPServer((host, port), MerisUiHandler)
    httpd.workspace = str(resolved)  # type: ignore[attr-defined]
    url = f"http://{host}:{port}/"
    print(f"Meris UI at {url}  (workspace: {resolved})", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Meris UI.", flush=True)
    finally:
        global _RUNTIME
        with _RUNTIME_LOCK:
            if _RUNTIME is not None:
                _RUNTIME.close()
                _RUNTIME = None
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Meris Agent Window — standalone web UI")
    parser.add_argument("--cwd", "-C", type=Path, default=Path.cwd())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", "-p", type=int, default=8765)
    args = parser.parse_args(argv)
    serve_ui(cwd=args.cwd, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
