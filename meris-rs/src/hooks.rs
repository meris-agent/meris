//! Hooks + Ratchet bridge via `meris harness hook` / `meris harness ratchet-record` (P5-4 M4).

use serde_json::Value;
use std::collections::HashMap;
use std::path::Path;
use std::process::Command;

#[derive(Debug, Clone, Default)]
pub struct HookResult {
    pub block: bool,
    pub message: String,
}

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

fn parse_hook_json(stdout: &str) -> Option<HookResult> {
    let v: Value = serde_json::from_str(stdout.trim()).ok()?;
    Some(HookResult {
        block: v.get("block").and_then(|b| b.as_bool()).unwrap_or(false),
        message: v
            .get("message")
            .and_then(|m| m.as_str())
            .unwrap_or("")
            .to_string(),
    })
}

pub fn has_tool_hooks(settings: &HashMap<String, Value>) -> bool {
    settings
        .get("hooks")
        .and_then(|h| h.as_object())
        .map(|o| {
            o.get("preToolUse")
                .and_then(|v| v.as_array())
                .is_some_and(|a| !a.is_empty())
                || o.get("postToolUse")
                    .and_then(|v| v.as_array())
                    .is_some_and(|a| !a.is_empty())
                || o.get("onSave")
                    .and_then(|v| v.as_array())
                    .is_some_and(|a| !a.is_empty())
        })
        .unwrap_or(false)
}

pub fn run_pre_hook(workspace: &Path, tool: &str, args: &Value) -> Option<HookResult> {
    let meris = which_meris()?;
    let ws = workspace.canonicalize().ok()?;
    let args_str = serde_json::to_string(args).ok()?;
    let output = Command::new(&meris)
        .args([
            "harness",
            "hook",
            "pre",
            "--cwd",
            ws.to_str()?,
            "--tool",
            tool,
            "--args",
            &args_str,
            "--json",
        ])
        .output()
        .ok()?;
    parse_hook_json(&String::from_utf8_lossy(&output.stdout))
}

pub fn run_post_hook(
    workspace: &Path,
    tool: &str,
    args: &Value,
    result: &str,
) -> Option<HookResult> {
    let meris = which_meris()?;
    let ws = workspace.canonicalize().ok()?;
    let args_str = serde_json::to_string(args).ok()?;
    let result_trim = if result.len() > 8000 {
        &result[..8000]
    } else {
        result
    };
    let output = Command::new(&meris)
        .args([
            "harness",
            "hook",
            "post",
            "--cwd",
            ws.to_str()?,
            "--tool",
            tool,
            "--args",
            &args_str,
            "--result",
            result_trim,
            "--json",
        ])
        .output()
        .ok()?;
    parse_hook_json(&String::from_utf8_lossy(&output.stdout))
}

pub fn run_on_save_hook(workspace: &Path, rel_path: &str) -> Option<HookResult> {
    let meris = which_meris()?;
    let ws = workspace.canonicalize().ok()?;
    let output = Command::new(&meris)
        .args([
            "harness",
            "hook",
            "on-save",
            "--cwd",
            ws.to_str()?,
            "--path",
            rel_path,
            "--json",
        ])
        .output()
        .ok()?;
    parse_hook_json(&String::from_utf8_lossy(&output.stdout))
}

pub fn record_ratchet_event(
    workspace: &Path,
    kind: &str,
    session: &str,
    task: &str,
    detail: &str,
    tool: &str,
) {
    let Some(meris) = which_meris() else {
        return;
    };
    let Ok(ws) = workspace.canonicalize() else {
        return;
    };
    let detail_trim: String = detail.chars().take(500).collect();
    let task_trim: String = task.chars().take(200).collect();
    let _ = Command::new(&meris)
        .args([
            "harness",
            "ratchet-record",
            "--cwd",
            ws.to_str().unwrap_or("."),
            "--kind",
            kind,
            "--session",
            session,
            "--task",
            &task_trim,
            "--detail",
            &detail_trim,
            "--tool",
            tool,
            "--json",
        ])
        .output();
}
