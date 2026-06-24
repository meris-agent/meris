//! System prompt bridge via `meris harness system-prompt --json` (P5-4 M5).

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

pub fn fallback_system_prompt(mode: &str) -> String {
    format!(
        "You are Meris, a harness-first coding agent. Mode: {mode}. \
         Use read_file/glob/grep for exploration; write_file/edit_file/bash when mode=run; \
         MCP tools are prefixed mcp_."
    )
}

pub fn load_system_prompt(workspace: &Path, mode: &str) -> String {
    load_system_prompt_bridge(workspace, mode).unwrap_or_else(|| fallback_system_prompt(mode))
}

fn load_system_prompt_bridge(workspace: &Path, mode: &str) -> Option<String> {
    let meris = which_meris()?;
    let ws = workspace.canonicalize().ok()?;
    let output = Command::new(&meris)
        .args([
            "harness",
            "system-prompt",
            "--cwd",
            ws.to_str()?,
            "--mode",
            mode,
            "--json",
        ])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let v: Value = serde_json::from_slice(&output.stdout).ok()?;
    v.get("prompt")
        .and_then(|p| p.as_str())
        .map(str::to_string)
        .filter(|s| !s.is_empty())
}
