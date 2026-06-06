const vscode = require("vscode");
const path = require("path");

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
  const folder = vscode.workspace.workspaceFolders?.[0];
  const cwd = folder?.uri.fsPath ?? ".";
  const term = vscode.window.createTerminal({ name: label, cwd });
  term.show();
  term.sendText(`meris ${command}`);
}

function runMerisWithEvents() {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    return;
  }
  const cwd = folder.uri.fsPath;
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

/** @param {vscode.ExtensionContext} context */
function activate(context) {
  context.subscriptions.push(
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
    )
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
