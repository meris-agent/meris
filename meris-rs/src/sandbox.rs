//! Bash sandbox — parity with meris.harness.sandbox (Phase E3).

use regex::Regex;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::Path;
use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

const DEFAULT_MODE: &str = "warn";
const DEFAULT_TIMEOUT: u64 = 120;

fn bash_rules() -> Vec<(Regex, &'static str)> {
    vec![
        (
            Regex::new(r"(?i)/workspace\b").unwrap(),
            "forbidden path `/workspace` — cwd is already repo root",
        ),
        (
            Regex::new(r"(?i)(?:^|[;&|]\s*|\s&&\s*)cd\s").unwrap(),
            "`cd` blocked — cwd is locked to workspace",
        ),
        (
            Regex::new(r"(?i)\bfind\s").unwrap(),
            "`find` blocked — use glob / grep / read_file",
        ),
        (
            Regex::new(r"(?i)\bpwd\b").unwrap(),
            "`pwd` blocked — use glob for pyproject.toml",
        ),
        (
            Regex::new(r"(?i)(?:^|[;&|]\s*|\s&&\s*)ls(?:\s|$)").unwrap(),
            "`ls` blocked — use glob / read_file",
        ),
    ]
}

pub fn get_sandbox_mode(settings: &HashMap<String, Value>) -> String {
    settings
        .get("sandbox")
        .and_then(|s| s.get("mode"))
        .and_then(|m| m.as_str())
        .map(|m| m.trim().to_lowercase())
        .filter(|m| matches!(m.as_str(), "off" | "warn" | "strict"))
        .unwrap_or_else(|| DEFAULT_MODE.to_string())
}

pub fn get_bash_timeout(settings: &HashMap<String, Value>) -> u64 {
    settings
        .get("sandbox")
        .and_then(|s| s.get("bashTimeoutSec"))
        .and_then(|t| t.as_u64().or_else(|| t.as_i64().map(|i| i as u64)))
        .map(|t| t.clamp(5, 3600))
        .unwrap_or(DEFAULT_TIMEOUT)
}

pub fn scan_bash_command(command: &str) -> Vec<String> {
    let cmd = command.trim();
    if cmd.is_empty() {
        return vec![];
    }
    let mut issues = Vec::new();
    for (rx, hint) in bash_rules() {
        if rx.is_match(cmd) {
            issues.push((*hint).to_string());
        }
    }
    issues
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SandboxVerdict {
    pub blocked: bool,
    pub message: String,
    pub mode: String,
}

pub fn check_bash_sandbox(command: &str, mode: &str) -> Option<SandboxVerdict> {
    if mode == "off" {
        return None;
    }
    let issues = scan_bash_command(command);
    if issues.is_empty() {
        return None;
    }
    let msg = issues[0].clone();
    if mode == "strict" {
        Some(SandboxVerdict {
            blocked: true,
            message: format!(
                "Sandbox (strict): {msg}. Use glob/read_file/pytest per .meris/rules/bash-permissions.md"
            ),
            mode: mode.to_string(),
        })
    } else {
        Some(SandboxVerdict {
            blocked: false,
            message: format!("{msg} (sandbox mode=warn — allowed but discouraged)"),
            mode: mode.to_string(),
        })
    }
}

pub fn verdict_to_json(v: &SandboxVerdict) -> Value {
    json!({
        "blocked": v.blocked,
        "message": v.message,
        "mode": v.mode,
    })
}

pub fn run_bash_in_workspace(
    workspace: &Path,
    command: &str,
    timeout_secs: u64,
) -> Result<(i32, String), String> {
    let ws = workspace
        .canonicalize()
        .map_err(|e| format!("workspace: {e}"))?;
    let mut cmd = if cfg!(windows) {
        let mut c = Command::new("cmd");
        c.args(["/C", command]);
        c
    } else {
        let mut c = Command::new("sh");
        c.args(["-c", command]);
        c
    };
    cmd.current_dir(&ws)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let (tx, rx) = std::sync::mpsc::channel();
    thread::spawn(move || {
        let result = cmd.output();
        let _ = tx.send(result);
    });

    match rx.recv_timeout(Duration::from_secs(timeout_secs.max(5))) {
        Ok(Ok(output)) => {
            let mut out = String::from_utf8_lossy(&output.stdout).into_owned();
            let err = String::from_utf8_lossy(&output.stderr);
            if !err.is_empty() {
                if !out.is_empty() {
                    out.push('\n');
                }
                out.push_str(&err);
            }
            let code = output.status.code().unwrap_or(1);
            if out.len() > 8000 {
                out = out[out.len().saturating_sub(8000)..].to_string();
            }
            Ok((code, out))
        }
        Ok(Err(e)) => Err(format!("spawn: {e}")),
        Err(_) => Err(format!("timeout after {timeout_secs}s")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scan_blocks_cd() {
        let issues = scan_bash_command("cd /tmp");
        assert!(issues.iter().any(|i| i.contains("cd")));
    }

    #[test]
    fn scan_allows_pytest() {
        assert!(scan_bash_command(r#"pytest tests/ -m "not integration" -q"#).is_empty());
    }

    #[test]
    fn strict_blocks_pwd() {
        let v = check_bash_sandbox("pwd", "strict").unwrap();
        assert!(v.blocked);
    }
}
