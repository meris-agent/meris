//! Review task bridge via `meris harness review-task --json` (Phase F2-M1).

use serde_json::Value;
use std::path::Path;
use std::process::Command;

fn which_meris() -> Option<String> {
    if cfg!(windows) {
        Command::new("where")
            .arg("meris")
            .output()
            .ok()
            .and_then(|o| {
                String::from_utf8(o.stdout)
                    .ok()
                    .and_then(|s| s.lines().next().map(str::trim).map(String::from))
            })
    } else {
        Command::new("which")
            .arg("meris")
            .output()
            .ok()
            .and_then(|o| {
                String::from_utf8(o.stdout)
                    .ok()
                    .map(|s| s.trim().to_string())
                    .filter(|s| !s.is_empty())
            })
    }
}

pub fn load_review_task(workspace: &Path, staged: bool) -> Option<String> {
    let meris = which_meris()?;
    let ws = workspace.canonicalize().ok()?;
    let mut cmd = Command::new(&meris);
    cmd.args([
        "harness",
        "review-task",
        "--cwd",
        ws.to_str()?,
        "--json",
    ]);
    if staged {
        cmd.arg("--staged");
    }
    let output = cmd.output().ok()?;
    if !output.status.success() {
        return None;
    }
    let v: Value = serde_json::from_slice(&output.stdout).ok()?;
    v.get("task")
        .and_then(|t| t.as_str())
        .map(str::to_string)
        .filter(|s| !s.is_empty())
}
