const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const { spawn, execFileSync } = require("child_process");

/** @type {vscode.ExtensionContext | null} */
let extensionContext = null;

/** @type {vscode.WebviewPanel | null} */
let agentPanel = null;

/** @type {Set<vscode.Webview>} */
const agentWebviews = new Set();

/** @type {import("child_process").ChildProcess | null} */
let activeProcess = null;

/** @type {{ path: string | null; position: number; pollTimer: ReturnType<typeof setInterval> | null; fsWatcher: fs.FSWatcher | null }} */
const tailState = { path: null, position: 0, pollTimer: null, fsWatcher: null };

function getWorkspaceCwd() {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function postToAgentWebviews(msg) {
  for (const webview of agentWebviews) {
    webview.postMessage(msg);
  }
}

/** @param {string} mode ask | plan | run */
async function runMerisTask(mode, extraArgs = []) {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    return;
  }
  const task = await vscode.window.showInputBox({
    prompt: `Meris ${mode} — describe your task`,
    placeHolder: "e.g. fix failing test in tests/test_auth.py",
  });
  if (!task) {
    return;
  }
  const escaped = task.replace(/"/g, '\\"');
  const args = [mode, `"${escaped}"`, ...extraArgs].join(" ");
  const term = vscode.window.createTerminal({
    name: `Meris ${mode}`,
    cwd: folder.uri.fsPath,
  });
  term.show();
  term.sendText(`meris ${args}`);
}

function runMerisSimple(command, label) {
  const cwd = getWorkspaceCwd() ?? ".";
  const term = vscode.window.createTerminal({ name: label, cwd });
  term.show();
  term.sendText(`meris ${command}`);
}

function runMerisWithEvents() {
  const cwd = getWorkspaceCwd();
  if (!cwd) {
    vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    return;
  }
  const eventsPath = path.join(cwd, ".meris", "events", "vscode-run.jsonl");
  runMerisTask("run", ["--event-stream", `"${eventsPath.replace(/\\/g, "/")}"`]);
}

async function runMerisReview() {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    return;
  }
  const staged = await vscode.window.showQuickPick(
    [
      { label: "Staged diff", value: "--staged" },
      { label: "Working tree diff", value: "" },
    ],
    { placeHolder: "Review which diff?" }
  );
  if (!staged) {
    return;
  }
  const term = vscode.window.createTerminal({
    name: "Meris Review",
    cwd: folder.uri.fsPath,
  });
  term.show();
  term.sendText(`meris review ${staged.value}`.trim());
}

async function runMerisExec() {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    return;
  }
  const task = await vscode.window.showInputBox({
    prompt: "Meris exec — one-shot task (JSON output)",
    placeHolder: "e.g. list files in src/",
  });
  if (!task) {
    return;
  }
  const escaped = task.replace(/"/g, '\\"');
  const term = vscode.window.createTerminal({
    name: "Meris Exec",
    cwd: folder.uri.fsPath,
  });
  term.show();
  term.sendText(`meris exec "${escaped}" --json`);
}

function getNonce() {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let out = "";
  for (let i = 0; i < 32; i++) {
    out += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return out;
}

/** @param {vscode.Webview} webview @param {vscode.Uri} extensionUri */
function getAgentWebviewContent(webview, extensionUri) {
  const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, "media", "agent.js"));
  const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, "media", "agent.css"));
  const nonce = getNonce();
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="${styleUri}" rel="stylesheet">
  <title>Meris Agent</title>
</head>
<body>
  <div id="header">
    <span class="brand">Meris Agent</span>
    <span id="status" class="status idle">Ready</span>
  </div>
  <div id="error-banner" class="hidden"></div>
  <div id="layout">
    <aside id="sessions-panel">
      <div class="panel-header">
        <span>Sessions</span>
        <button id="refresh-sessions" title="Refresh">↻</button>
      </div>
      <ul id="session-list"></ul>
    </aside>
    <div id="main">
      <div id="timeline"></div>
      <div id="composer">
        <div id="approval-bar" class="hidden">
          <div class="approval-title">Approve tool call?</div>
          <div id="approval-tool" class="approval-tool"></div>
          <pre id="approval-args" class="approval-args"></pre>
          <div class="approval-actions">
            <button id="approve-yes" type="button">Approve</button>
            <button id="approve-no" type="button">Deny</button>
          </div>
        </div>
        <textarea id="task-input" placeholder="Describe your task…" rows="2"></textarea>
        <div id="composer-actions">
          <select id="mode-select">
            <option value="run" selected>run</option>
            <option value="ask">ask</option>
            <option value="plan">plan</option>
          </select>
          <label><input type="checkbox" id="approve-check"> approve</label>
          <button id="submit-btn">Run</button>
          <button id="stop-btn" disabled>Stop</button>
        </div>
      </div>
    </div>
    <aside id="ratchet-panel">
      <div class="panel-header">
        <span>Ratchet</span>
        <div class="panel-actions">
          <button id="ratchet-scan" title="Scan">⊕</button>
          <button id="refresh-ratchet" title="Refresh">↻</button>
        </div>
      </div>
      <ul id="ratchet-list"></ul>
    </aside>
  </div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
}

function stopTail() {
  if (tailState.pollTimer) {
    clearInterval(tailState.pollTimer);
    tailState.pollTimer = null;
  }
  if (tailState.fsWatcher) {
    tailState.fsWatcher.close();
    tailState.fsWatcher = null;
  }
}

/** @param {string} eventsPath @returns {object[]} */
function readNewJsonlEvents(eventsPath) {
  if (!fs.existsSync(eventsPath)) {
    return [];
  }
  const stat = fs.statSync(eventsPath);
  if (stat.size < tailState.position) {
    tailState.position = 0;
  }
  if (stat.size === tailState.position) {
    return [];
  }
  const fd = fs.openSync(eventsPath, "r");
  const buffer = Buffer.alloc(stat.size - tailState.position);
  fs.readSync(fd, buffer, 0, buffer.length, tailState.position);
  fs.closeSync(fd);
  tailState.position = stat.size;

  const events = [];
  for (const line of buffer.toString("utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }
    try {
      events.push(JSON.parse(trimmed));
    } catch {
      // skip malformed line
    }
  }
  return events;
}

/** @param {string} eventsPath @param {(ev: object) => void} onEvent */
function startJsonlTail(eventsPath, onEvent) {
  stopTail();
  tailState.path = eventsPath;
  tailState.position = 0;

  const dir = path.dirname(eventsPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  if (fs.existsSync(eventsPath)) {
    tailState.position = fs.statSync(eventsPath).size;
  }

  const pump = () => {
    for (const ev of readNewJsonlEvents(eventsPath)) {
      onEvent(ev);
    }
  };

  tailState.pollTimer = setInterval(pump, 250);
  try {
    tailState.fsWatcher = fs.watch(eventsPath, pump);
  } catch {
    // file may not exist until meris writes
  }
}

function killActiveProcess() {
  if (activeProcess && !activeProcess.killed) {
    activeProcess.kill("SIGTERM");
    activeProcess = null;
  }
}

/** @param {string} cwd @returns {object[]} */
function loadSessions(cwd) {
  const dir = path.join(cwd, ".meris", "sessions");
  if (!fs.existsSync(dir)) {
    return [];
  }
  const sessions = [];
  for (const name of fs.readdirSync(dir)) {
    if (!name.endsWith(".json")) {
      continue;
    }
    const fp = path.join(dir, name);
    try {
      const data = JSON.parse(fs.readFileSync(fp, "utf8"));
      const stat = fs.statSync(fp);
      sessions.push({
        id: data.id || name.replace(/\.json$/, ""),
        task: data.task || "",
        mode: data.mode || "run",
        status: data.status || "unknown",
        turn: data.turn || 0,
        updatedAt: data.updated_at || "",
        mtime: stat.mtimeMs,
      });
    } catch {
      // skip corrupt session file
    }
  }
  return sessions.sort((a, b) => b.mtime - a.mtime).slice(0, 20);
}

/** @param {string} cwd */
function loadRatchetData(cwd) {
  const proposalsDir = path.join(cwd, ".meris", "ratchet", "proposals");
  const proposals = [];
  if (fs.existsSync(proposalsDir)) {
    for (const name of fs.readdirSync(proposalsDir)) {
      if (!name.endsWith(".json")) {
        continue;
      }
      const fp = path.join(proposalsDir, name);
      try {
        const data = JSON.parse(fs.readFileSync(fp, "utf8"));
        if (data.status !== "pending") {
          continue;
        }
        const stat = fs.statSync(fp);
        proposals.push({
          id: data.id,
          lesson: data.lesson || "",
          summary: data.summary || "",
          target: data.target?.path || "",
          mtime: stat.mtimeMs,
        });
      } catch {
        // skip
      }
    }
  }
  proposals.sort((a, b) => b.mtime - a.mtime);

  let insightsPending = 0;
  const insightsPath = path.join(cwd, ".meris", "ratchet", "insights", "pending.jsonl");
  if (fs.existsSync(insightsPath)) {
    insightsPending = fs
      .readFileSync(insightsPath, "utf8")
      .split("\n")
      .filter((line) => line.trim()).length;
  }

  return { proposals: proposals.slice(0, 8), insightsPending };
}

/** @param {string} cwd */
function refreshAgentSidebarData(cwd) {
  postToAgentWebviews({ type: "sessions", sessions: loadSessions(cwd) });
  postToAgentWebviews({ type: "ratchet", ...loadRatchetData(cwd) });
}

/** @param {string} cwd */
function runRatchetScan(cwd) {
  return new Promise((resolve) => {
    const proc = spawn("meris", ["ratchet", "scan"], {
      cwd,
      shell: true,
      env: { ...process.env },
    });
    let stderr = "";
    proc.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("close", (code) => {
      resolve({ ok: code === 0, stderr: stderr.slice(-300) });
    });
  });
}

/** @param {string} cwd @param {string} subcmd apply | reject @param {string} proposalId */
function runRatchetCli(cwd, subcmd, proposalId) {
  return new Promise((resolve) => {
    const proc = spawn("meris", ["ratchet", subcmd, proposalId], {
      cwd,
      shell: true,
      env: { ...process.env },
    });
    let stderr = "";
    proc.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("close", (code) => {
      resolve({ ok: code === 0, stderr: stderr.slice(-300) });
    });
  });
}

/** @param {string} cwd @param {(ev: object) => void} postEvent @returns {string[]} */
function buildMerisSpawnArgs(cwd, postEvent, opts) {
  const eventsPath = path.join(cwd, ".meris", "events", "agent-window.jsonl");
  const eventsArg = eventsPath.replace(/\\/g, "/");
  const approvalArg = path.join(cwd, ".meris", "events", "approval").replace(/\\/g, "/");

  const eventDir = path.dirname(eventsPath);
  if (!fs.existsSync(eventDir)) {
    fs.mkdirSync(eventDir, { recursive: true });
  }
  fs.writeFileSync(eventsPath, "", "utf8");

  startJsonlTail(eventsPath, postEvent);

  const approvalFlags = [];
  if (opts.approve) {
    approvalFlags.push("--approve", "--approval-channel", approvalArg);
  }

  if (opts.resume && opts.sessionId) {
    return ["session", "resume", opts.sessionId, "--event-stream", eventsArg, ...approvalFlags];
  }

  return [opts.mode, opts.task, "--event-stream", eventsArg, ...approvalFlags];
}

/** @param {string} cwd @param {string} requestId @param {boolean} approved */
function writeApprovalResponse(cwd, requestId, approved) {
  const dir = path.join(cwd, ".meris", "events", "approval");
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const resPath = path.join(dir, "approval-response.json");
  fs.writeFileSync(resPath, JSON.stringify({ request_id: requestId, approved }), "utf8");
}

function getGitDiff(cwd, relPath) {
  if (!relPath) {
    return "";
  }
  try {
    return execFileSync("git", ["diff", "--unified=3", "--", relPath], {
      cwd,
      encoding: "utf8",
      maxBuffer: 80000,
    }).trim();
  } catch (err) {
    const out = err.stdout ? String(err.stdout).trim() : "";
    return out;
  }
}

/** @param {string} cwd @param {object} ev */
function enrichEvent(cwd, ev) {
  if (!ev || ev.kind !== "file_change" || ev.diff_preview) {
    return ev;
  }
  const gitDiff = getGitDiff(cwd, ev.path);
  if (!gitDiff) {
    return ev;
  }
  return { ...ev, diff_preview: gitDiff };
}

/** @param {string} cwd @param {object} opts */
function spawnMerisRun(cwd, opts) {
  const eventsPath = path.join(cwd, ".meris", "events", "agent-window.jsonl");
  const postEvent = (ev) => {
    postToAgentWebviews({ type: "event", event: enrichEvent(cwd, ev) });
  };

  const args = buildMerisSpawnArgs(cwd, postEvent, opts);

  killActiveProcess();
  activeProcess = spawn("meris", args, {
    cwd,
    shell: true,
    env: { ...process.env },
  });

  let stderr = "";
  activeProcess.stderr?.on("data", (chunk) => {
    stderr += chunk.toString();
  });

  activeProcess.on("close", (code) => {
    for (const ev of readNewJsonlEvents(eventsPath)) {
      postEvent(ev);
    }
    activeProcess = null;
    const status = code === 0 ? "done" : "error";
    postToAgentWebviews({
      type: "status",
      status,
      code,
      stderr: stderr.slice(-500),
    });
    refreshAgentSidebarData(cwd);
  });
}

/** @param {object} msg */
async function handleAgentMessage(msg) {
  const cwd = getWorkspaceCwd();
  if (!cwd) {
    if (msg.type === "submit" || msg.type === "resumeSession") {
      vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    }
    return;
  }

  switch (msg.type) {
    case "submit":
      postToAgentWebviews({ type: "runStart", task: msg.task, mode: msg.mode });
      postToAgentWebviews({ type: "status", status: "running" });
      spawnMerisRun(cwd, {
        task: msg.task,
        mode: msg.mode,
        approve: Boolean(msg.approve),
        resume: false,
      });
      break;
    case "resumeSession": {
      const sessions = loadSessions(cwd);
      const rec = sessions.find((s) => s.id === msg.sessionId);
      if (!rec) {
        vscode.window.showErrorMessage(`Meris: session not found: ${msg.sessionId}`);
        return;
      }
      postToAgentWebviews({
        type: "runStart",
        task: rec.task,
        mode: rec.mode,
        resume: true,
        sessionId: msg.sessionId,
      });
      postToAgentWebviews({ type: "status", status: "running" });
      spawnMerisRun(cwd, {
        task: rec.task,
        mode: rec.mode,
        approve: Boolean(msg.approve),
        resume: true,
        sessionId: msg.sessionId,
      });
      break;
    }
    case "refreshSessions":
    case "refreshRatchet":
      refreshAgentSidebarData(cwd);
      break;
    case "approvalResponse":
      if (msg.requestId) {
        writeApprovalResponse(cwd, msg.requestId, Boolean(msg.approved));
      }
      break;
    case "openFile": {
      if (!msg.path) return;
      const full = path.isAbsolute(msg.path) ? msg.path : path.join(cwd, msg.path);
      const uri = vscode.Uri.file(full);
      const doc = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(doc, { preview: false });
      break;
    }
    case "ratchetApply":
    case "ratchetReject": {
      if (!msg.proposalId) return;
      const subcmd = msg.type === "ratchetApply" ? "apply" : "reject";
      const result = await runRatchetCli(cwd, subcmd, msg.proposalId);
      postToAgentWebviews({
        type: "ratchetResult",
        action: subcmd,
        proposalId: msg.proposalId,
        ok: result.ok,
        detail: result.stderr,
      });
      refreshAgentSidebarData(cwd);
      break;
    }
    case "ratchetScan": {
      const result = await runRatchetScan(cwd);
      postToAgentWebviews({
        type: "ratchetResult",
        action: "scan",
        ok: result.ok,
        detail: result.stderr || (result.ok ? "scan complete" : "scan failed"),
      });
      refreshAgentSidebarData(cwd);
      break;
    }
    case "stop":
      killActiveProcess();
      postToAgentWebviews({ type: "status", status: "cancelled" });
      refreshAgentSidebarData(cwd);
      break;
    default:
      break;
  }
}

/** @param {vscode.Webview} webview */
function registerAgentWebview(webview) {
  agentWebviews.add(webview);
  webview.onDidReceiveMessage(handleAgentMessage);
}

/** @param {vscode.ExtensionContext} context */
function setupAgentWebview(webview, context) {
  const extensionUri = context.extensionUri;
  webview.options = {
    enableScripts: true,
    localResourceRoots: [vscode.Uri.joinPath(extensionUri, "media")],
  };
  webview.html = getAgentWebviewContent(webview, extensionUri);
  registerAgentWebview(webview);
  const cwd = getWorkspaceCwd();
  if (cwd) {
    refreshAgentSidebarData(cwd);
  }
}

class MerisAgentViewProvider {
  /** @param {vscode.ExtensionContext} context */
  constructor(context) {
    this.context = context;
  }

  /** @param {vscode.WebviewView} webviewView */
  resolveWebviewView(webviewView) {
    setupAgentWebview(webviewView.webview, this.context);
    webviewView.onDidDispose(() => {
      agentWebviews.delete(webviewView.webview);
    });
  }
}

/** @param {vscode.ExtensionContext} context */
function openAgentWindow(context) {
  if (agentPanel) {
    agentPanel.reveal(vscode.ViewColumn.Beside);
    return;
  }

  agentPanel = vscode.window.createWebviewPanel(
    "merisAgentWindow",
    "Meris Agent",
    vscode.ViewColumn.Beside,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, "media")],
    }
  );

  setupAgentWebview(agentPanel.webview, context);

  agentPanel.onDidDispose(() => {
    agentWebviews.delete(agentPanel.webview);
    stopTail();
    killActiveProcess();
    agentPanel = null;
  });
}

/** @param {vscode.ExtensionContext} context */
function activate(context) {
  extensionContext = context;

  const viewProvider = new MerisAgentViewProvider(context);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("meris.agentView", viewProvider, {
      webviewOptions: { retainContextWhenHidden: true },
    }),
    vscode.commands.registerCommand("meris.ask", () => runMerisTask("ask")),
    vscode.commands.registerCommand("meris.plan", () => runMerisTask("plan")),
    vscode.commands.registerCommand("meris.run", () => runMerisTask("run")),
    vscode.commands.registerCommand("meris.runApprove", () =>
      runMerisTask("run", ["--approve"])
    ),
    vscode.commands.registerCommand("meris.runWithEvents", runMerisWithEvents),
    vscode.commands.registerCommand("meris.review", runMerisReview),
    vscode.commands.registerCommand("meris.exec", runMerisExec),
    vscode.commands.registerCommand("meris.doctor", () =>
      runMerisSimple("doctor", "Meris Doctor")
    ),
    vscode.commands.registerCommand("meris.tui", () =>
      runMerisSimple("tui", "Meris TUI")
    ),
    vscode.commands.registerCommand("meris.agentWindow", () => openAgentWindow(context)),
    vscode.commands.registerCommand("meris.agentView.focus", () => {
      vscode.commands.executeCommand("workbench.view.extension.meris-sidebar");
    })
  );
}

function deactivate() {
  stopTail();
  killActiveProcess();
  agentWebviews.clear();
}

module.exports = { activate, deactivate };
