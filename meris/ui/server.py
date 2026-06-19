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
        payload = json.dumps(msg, ensure_ascii=False)
        with self.lock:
            subs = list(self.subscribers)
        for cond in subs:
            with cond:
                if not hasattr(cond, "_queue"):
                    cond._queue = []  # type: ignore[attr-defined]
                cond._queue.append(payload)  # type: ignore[attr-defined]
                cond.notify()

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

    def spawn_run(self, *, task: str, mode: str, approve: bool, resume: bool, session_id: str) -> None:
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
                self.stderr = ""
                self.proc = None
            status = "done" if code == 0 else "error"
            self.broadcast(
                {
                    "type": "status",
                    "status": status,
                    "code": code,
                    "stderr": self.stderr,
                }
            )
            self.broadcast({"type": "sessions", "sessions": load_sessions(self.cwd)})
            self.broadcast({"type": "ratchet", **load_ratchet(self.cwd)})

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
            self.broadcast({"type": "sessions", "sessions": load_sessions(self.cwd)})

        threading.Thread(target=_wait, daemon=True).start()


_RUNTIME: UiRuntime | None = None
_RUNTIME_LOCK = threading.Lock()


def get_runtime(cwd: Path) -> UiRuntime:
    global _RUNTIME
    with _RUNTIME_LOCK:
        resolved = cwd.resolve()
        if _RUNTIME is None or _RUNTIME.cwd != resolved:
            if _RUNTIME is not None:
                _RUNTIME.close()
            _RUNTIME = UiRuntime(resolved)
        return _RUNTIME


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

        self.send_error(HTTPStatus.NOT_FOUND)

    def _handle_sse(self) -> None:
        cond = self.runtime.subscribe()
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
            self.runtime.unsubscribe(cond)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
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
        elif mtype == "listContextFiles":
            rt.broadcast({"type": "contextFiles", "files": _list_workspace_files(cwd, str(msg.get("query") or ""))})
        elif mtype == "readContextFile":
            try:
                item = _read_workspace_file(cwd, str(msg.get("path") or ""))
                rt.broadcast({"type": "contextItem", "item": item})
            except (OSError, ValueError):
                pass
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

        self._send_json({"ok": True})


def serve_ui(*, cwd: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    get_runtime(cwd)
    httpd = ThreadingHTTPServer((host, port), MerisUiHandler)
    httpd.workspace = str(cwd.resolve())  # type: ignore[attr-defined]
    url = f"http://{host}:{port}/"
    print(f"Meris UI at {url}  (workspace: {cwd.resolve()})", flush=True)
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
