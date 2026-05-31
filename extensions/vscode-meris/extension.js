const vscode = require("vscode");

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

/** @param {vscode.ExtensionContext} context */
function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("meris.ask", () => runMerisTask("ask")),
    vscode.commands.registerCommand("meris.plan", () => runMerisTask("plan")),
    vscode.commands.registerCommand("meris.run", () => runMerisTask("run")),
    vscode.commands.registerCommand("meris.runApprove", () =>
      runMerisTask("run", ["--approve"])
    ),
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
