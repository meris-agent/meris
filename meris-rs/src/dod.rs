//! DoD failure bridge via `meris harness dod-failed --json` (Phase F2-M3).

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

pub fn handle_dod_failed(
    workspace: &Path,
    session: &str,
    task: &str,
    mode: &str,
    sensor_out: &str,
) -> Vec<String> {
    let Some(meris) = which_meris() else {
        return vec!["[ratchet] meris ratchet scan — capture harness improvements".into()];
    };
    let Ok(ws) = workspace.canonicalize() else {
        return vec!["[ratchet] meris ratchet scan — capture harness improvements".into()];
    };
    let detail: String = sensor_out.chars().take(800).collect();
    let task_trim: String = task.chars().take(200).collect();
    let output = Command::new(&meris)
        .args([
            "harness",
            "dod-failed",
            "--cwd",
            ws.to_str().unwrap_or("."),
            "--session",
            session,
            "--task",
            &task_trim,
            "--mode",
            mode,
            "--detail",
            &detail,
            "--json",
        ])
        .output();
    let Ok(out) = output else {
        return vec!["[ratchet] meris ratchet scan — capture harness improvements".into()];
    };
    if !out.status.success() {
        return vec!["[ratchet] meris ratchet scan — capture harness improvements".into()];
    }
    let v: Value = match serde_json::from_slice(&out.stdout) {
        Ok(v) => v,
        Err(_) => return vec!["[ratchet] meris ratchet scan — capture harness improvements".into()],
    };
    v.get("hints")
        .and_then(|h| h.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_else(|| vec!["[ratchet] meris ratchet scan — capture harness improvements".into()])
}
