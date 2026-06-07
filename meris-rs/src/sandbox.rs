//! Bash sandbox — policy scan + cwd-locked run + optional Linux bubblewrap (Phase E3).

#[path = "sandbox_macos.rs"]
mod sandbox_macos;

pub use sandbox_macos::{build_seatbelt_policy, find_sandbox_exec, run_bash_seatbelt, should_use_seatbelt};

use regex::Regex;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

const DEFAULT_MODE: &str = "warn";
const DEFAULT_TIMEOUT: u64 = 120;
const DEFAULT_OS_SANDBOX: &str = "auto";
const DEFAULT_NETWORK: &str = "isolated";
const DEFAULT_PRESET: &str = "workspace-write";

fn preset_field(preset: &str, field: &str) -> Option<&'static str> {
    match (preset, field) {
        ("read-only", "mode") => Some("strict"),
        ("read-only", "network") => Some("isolated"),
        ("read-only", "osSandbox") => Some("auto"),
        ("workspace-write", "mode") => Some("warn"),
        ("workspace-write", "network") => Some("isolated"),
        ("workspace-write", "osSandbox") => Some("auto"),
        ("danger-full-access", "mode") => Some("off"),
        ("danger-full-access", "network") => Some("shared"),
        ("danger-full-access", "osSandbox") => Some("off"),
        _ => None,
    }
}

fn get_sandbox_preset(settings: &HashMap<String, Value>) -> String {
    settings
        .get("sandbox")
        .and_then(|s| s.get("preset"))
        .and_then(|v| v.as_str())
        .map(|p| p.trim().to_lowercase())
        .filter(|p| {
            matches!(
                p.as_str(),
                "read-only" | "workspace-write" | "danger-full-access"
            )
        })
        .unwrap_or_else(|| DEFAULT_PRESET.to_string())
}

fn resolve_sandbox_field(
    settings: &HashMap<String, Value>,
    field: &str,
    valid: &[&str],
    hard_default: &str,
) -> String {
    if let Some(raw) = settings
        .get("sandbox")
        .and_then(|s| s.get(field))
        .and_then(|v| v.as_str())
    {
        let val = raw.trim().to_lowercase();
        if valid.contains(&val.as_str()) {
            return val;
        }
    }
    let preset = get_sandbox_preset(settings);
    if let Some(from_preset) = preset_field(&preset, field) {
        return from_preset.to_string();
    }
    hard_default.to_string()
}

const DEFAULT_MASK_REL: &[&str] = &[
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
];

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
    resolve_sandbox_field(settings, "mode", &["off", "warn", "strict"], DEFAULT_MODE)
}

pub fn get_os_sandbox_mode(settings: &HashMap<String, Value>) -> String {
    resolve_sandbox_field(
        settings,
        "osSandbox",
        &["off", "auto", "require"],
        DEFAULT_OS_SANDBOX,
    )
}

pub fn get_network_mode(settings: &HashMap<String, Value>) -> String {
    resolve_sandbox_field(
        settings,
        "network",
        &["shared", "isolated", "allowlist"],
        DEFAULT_NETWORK,
    )
}

pub fn get_network_allowlist(settings: &HashMap<String, Value>) -> Vec<String> {
    let Some(arr) = settings
        .get("sandbox")
        .and_then(|s| s.get("networkAllowlist"))
        .and_then(|v| v.as_array())
    else {
        return vec![];
    };
    let mut out = Vec::new();
    for item in arr {
        if let Some(s) = item.as_str() {
            let pat = s.trim().to_lowercase();
            if !pat.is_empty() && !out.contains(&pat) {
                out.push(pat);
            }
        }
    }
    out
}

pub fn get_effective_network_mode(settings: &HashMap<String, Value>) -> String {
    let mode = get_network_mode(settings);
    if mode == "allowlist" {
        return "allowlist".to_string();
    }
    if mode == "isolated" && !get_network_allowlist(settings).is_empty() {
        return "allowlist".to_string();
    }
    mode
}

pub fn host_allowed(host: &str, pattern: &str) -> bool {
    let host = host.trim().trim_matches('.').to_lowercase();
    let pat = pattern.trim().to_lowercase();
    if host.is_empty() || pat.is_empty() {
        return false;
    }
    if let Some(base) = pat.strip_prefix("*.") {
        return host == base || host.ends_with(&format!(".{base}"));
    }
    host == pat || host.ends_with(&format!(".{pat}"))
}

pub fn extract_network_hosts(command: &str) -> Vec<String> {
    let url_re = Regex::new("(?i)https?://([^/\\s'\"#?]+)").unwrap();
    let git_re = Regex::new(r"(?i)git@([^:/\s]+)").unwrap();
    let ssh_re = Regex::new(r"(?i)\bssh\s+(?:[^\s@]+\@)?([^\s:/]+)").unwrap();
    let mut seen = std::collections::HashSet::new();
    let mut hosts = Vec::new();
    for re in [&url_re, &git_re, &ssh_re] {
        for cap in re.captures_iter(command) {
            if let Some(m) = cap.get(1) {
                let h = m.as_str().trim().trim_matches('.').to_lowercase();
                if !h.is_empty() && seen.insert(h.clone()) {
                    hosts.push(h);
                }
            }
        }
    }
    hosts
}

pub fn check_network_allowlist(command: &str, settings: &HashMap<String, Value>) -> Option<String> {
    if get_effective_network_mode(settings) != "allowlist" {
        return None;
    }
    let allowlist = get_network_allowlist(settings);
    if allowlist.is_empty() {
        return Some("network allowlist mode but sandbox.networkAllowlist is empty".into());
    }
    let tool_re = Regex::new(r"(?i)\b(curl|wget|pip\s+install|npm\s+install|git\s+clone|ssh)\b").unwrap();
    if !tool_re.is_match(command) {
        return None;
    }
    let hosts = extract_network_hosts(command);
    if hosts.is_empty() {
        return Some("network command without parseable host — not in networkAllowlist".into());
    }
    for host in hosts {
        if !allowlist.iter().any(|p| host_allowed(&host, p)) {
            return Some(format!("host `{host}` not in sandbox.networkAllowlist"));
        }
    }
    None
}

pub fn get_mask_secrets(settings: &HashMap<String, Value>) -> bool {
    settings
        .get("sandbox")
        .and_then(|s| s.get("maskSecrets"))
        .and_then(|v| v.as_bool())
        .unwrap_or(true)
}

pub fn collect_mask_paths(workspace: &Path, settings: &HashMap<String, Value>) -> Vec<PathBuf> {
    if !get_mask_secrets(settings) {
        return vec![];
    }
    let ws = match workspace.canonicalize() {
        Ok(p) => p,
        Err(_) => return vec![],
    };
    let mut rels: Vec<String> = DEFAULT_MASK_REL.iter().map(|s| (*s).to_string()).collect();
    if let Some(extra) = settings.get("sandbox").and_then(|s| s.get("maskPaths")).and_then(|v| v.as_array())
    {
        for item in extra {
            if let Some(s) = item.as_str() {
                let t = s.trim().replace('\\', "/");
                if !t.is_empty() {
                    rels.push(t);
                }
            }
        }
    }
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for rel in rels {
        if !seen.insert(rel.clone()) {
            continue;
        }
        let p = ws.join(&rel);
        if p.is_file() {
            out.push(p);
        }
    }
    out
}

pub fn get_bash_timeout(settings: &HashMap<String, Value>) -> u64 {
    settings
        .get("sandbox")
        .and_then(|s| s.get("bashTimeoutSec"))
        .and_then(|t| t.as_u64().or_else(|| t.as_i64().map(|i| i as u64)))
        .map(|t| t.clamp(5, 3600))
        .unwrap_or(DEFAULT_TIMEOUT)
}

pub fn find_bubblewrap() -> Option<PathBuf> {
    if !cfg!(target_os = "linux") {
        return None;
    }
    let path_var = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path_var) {
        for name in ["bwrap", "bubblewrap"] {
            let candidate = dir.join(name);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

pub fn bubblewrap_version(bwrap: &Path) -> Option<String> {
    Command::new(bwrap)
        .arg("--version")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .ok()
        .map(|out| String::from_utf8_lossy(&out.stdout).trim().to_string())
        .filter(|s| !s.is_empty())
}

pub fn should_use_bubblewrap(settings: &HashMap<String, Value>) -> Result<bool, String> {
    if !cfg!(target_os = "linux") {
        return Ok(false);
    }
    match get_os_sandbox_mode(settings).as_str() {
        "off" => Ok(false),
        "require" => {
            if find_bubblewrap().is_some() {
                Ok(true)
            } else {
                Err("sandbox.osSandbox=require but bubblewrap (bwrap) not found on PATH".into())
            }
        }
        "auto" | _ => Ok(find_bubblewrap().is_some()),
    }
}

pub fn os_sandbox_probe(settings: &HashMap<String, Value>) -> Value {
    let os_mode = get_os_sandbox_mode(settings);
    let bwrap = find_bubblewrap();
    let version = bwrap.as_ref().and_then(|p| bubblewrap_version(p));
    let would_bwrap = should_use_bubblewrap(settings).unwrap_or(false);
    let would_seatbelt = should_use_seatbelt(settings).unwrap_or(false);
    let network = get_effective_network_mode(settings);
    let allowlist = get_network_allowlist(settings);
    let mask_secrets = get_mask_secrets(settings);
    let sandbox_exec = find_sandbox_exec();
    json!({
        "platform": std::env::consts::OS,
        "preset": get_sandbox_preset(settings),
        "osSandbox": os_mode,
        "network": network,
        "networkAllowlist": allowlist,
        "maskSecrets": mask_secrets,
        "bubblewrap": bwrap.map(|p| p.to_string_lossy().to_string()),
        "bubblewrapVersion": version,
        "wouldUseBubblewrap": would_bwrap,
        "sandboxExec": sandbox_exec.map(|p| p.to_string_lossy().to_string()),
        "wouldUseSeatbelt": would_seatbelt,
    })
}

pub fn os_sandbox_probe_workspace(workspace: &Path, settings: &HashMap<String, Value>) -> Value {
    let mut probe = os_sandbox_probe(settings);
    if let Some(obj) = probe.as_object_mut() {
        let masked: Vec<String> = collect_mask_paths(workspace, settings)
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect();
        obj.insert("maskedPaths".into(), json!(masked));
    }
    probe
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

pub fn check_bash_sandbox(
    command: &str,
    mode: &str,
    settings: &HashMap<String, Value>,
) -> Option<SandboxVerdict> {
    if mode == "off" {
        return None;
    }
    let mut issues = scan_bash_command(command);
    if let Some(net) = check_network_allowlist(command, settings) {
        issues.insert(0, net);
    }
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

pub(crate) fn run_command_with_timeout(
    mut cmd: Command,
    timeout_secs: u64,
) -> Result<(i32, String), String> {
    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
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

fn build_bwrap_command(
    bwrap: &Path,
    workspace: &Path,
    command: &str,
    settings: &HashMap<String, Value>,
) -> Result<Command, String> {
    let ws = workspace
        .canonicalize()
        .map_err(|e| format!("workspace: {e}"))?;
    let ws_s = ws.to_string_lossy();
    let mut cmd = Command::new(bwrap);
    cmd.arg("--ro-bind").arg("/").arg("/");
    cmd.arg("--bind").arg(ws_s.as_ref()).arg(ws_s.as_ref());
    for mask in collect_mask_paths(&ws, settings) {
        let ms = mask.to_string_lossy();
        cmd.arg("--ro-bind").arg("/dev/null").arg(ms.as_ref());
    }
    cmd.args([
        "--tmpfs",
        "/tmp",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--die-with-parent",
        "--new-session",
        "--unshare-pid",
    ]);
    if get_effective_network_mode(settings) == "isolated" {
        cmd.arg("--unshare-net");
    } else {
        cmd.arg("--share-net");
    }
    cmd.arg("--chdir").arg(ws_s.as_ref());
    cmd.arg("sh").arg("-c").arg(command);
    Ok(cmd)
}

pub fn run_bash_bubblewrap(
    workspace: &Path,
    command: &str,
    timeout_secs: u64,
    settings: &HashMap<String, Value>,
) -> Result<(i32, String), String> {
    let bwrap = find_bubblewrap().ok_or_else(|| "bubblewrap (bwrap) not found".to_string())?;
    let cmd = build_bwrap_command(&bwrap, workspace, command, settings)?;
    run_command_with_timeout(cmd, timeout_secs)
}

pub fn run_bash_plain(
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
    cmd.current_dir(&ws);
    run_command_with_timeout(cmd, timeout_secs)
}

pub fn run_bash_in_workspace(
    workspace: &Path,
    command: &str,
    timeout_secs: u64,
    settings: &HashMap<String, Value>,
) -> Result<(i32, String), String> {
    if should_use_bubblewrap(settings)? {
        run_bash_bubblewrap(workspace, command, timeout_secs, settings)
    } else if should_use_seatbelt(settings)? {
        run_bash_seatbelt(workspace, command, timeout_secs, settings)
    } else {
        run_bash_plain(workspace, command, timeout_secs)
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
        let v = check_bash_sandbox("pwd", "strict", &HashMap::new()).unwrap();
        assert!(v.blocked);
    }

    #[test]
    fn default_os_sandbox_auto() {
        let settings = HashMap::new();
        assert_eq!(get_os_sandbox_mode(&settings), "auto");
    }

    #[test]
    fn os_sandbox_off_skips_bwrap() {
        let mut settings = HashMap::new();
        settings.insert("sandbox".into(), json!({"osSandbox": "off"}));
        assert!(!should_use_bubblewrap(&settings).unwrap());
    }

    #[test]
    fn network_isolated_mode() {
        let mut settings = HashMap::new();
        settings.insert("sandbox".into(), json!({"network": "isolated"}));
        assert_eq!(get_network_mode(&settings), "isolated");
    }

    #[test]
    fn preset_workspace_write_default_network() {
        let settings = HashMap::new();
        assert_eq!(get_sandbox_preset(&settings), "workspace-write");
        assert_eq!(get_network_mode(&settings), "isolated");
        assert_eq!(get_sandbox_mode(&settings), "warn");
    }

    #[test]
    fn preset_danger_full_access() {
        let mut settings = HashMap::new();
        settings.insert(
            "sandbox".into(),
            json!({"preset": "danger-full-access"}),
        );
        assert_eq!(get_network_mode(&settings), "shared");
        assert_eq!(get_sandbox_mode(&settings), "off");
    }

    #[test]
    fn mask_paths_skipped_when_disabled() {
        let dir = tempfile::tempdir().unwrap();
        let env = dir.path().join(".env");
        std::fs::write(&env, "SECRET=1").unwrap();
        let mut settings = HashMap::new();
        settings.insert("sandbox".into(), json!({"maskSecrets": false}));
        assert!(collect_mask_paths(dir.path(), &settings).is_empty());
    }

    #[test]
    fn mask_paths_includes_env() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join(".env"), "SECRET=1").unwrap();
        let settings = HashMap::new();
        let masked = collect_mask_paths(dir.path(), &settings);
        assert_eq!(masked.len(), 1);
    }

    #[test]
    fn allowlist_effective_mode() {
        let mut settings = HashMap::new();
        settings.insert(
            "sandbox".into(),
            json!({
                "network": "isolated",
                "networkAllowlist": ["github.com"]
            }),
        );
        assert_eq!(get_effective_network_mode(&settings), "allowlist");
    }

    #[test]
    fn allowlist_blocks_unknown_host() {
        let mut settings = HashMap::new();
        settings.insert(
            "sandbox".into(),
            json!({"networkAllowlist": ["api.deepseek.com"]}),
        );
        let msg = check_network_allowlist(
            "curl https://evil.example.com/x",
            &settings,
        );
        assert!(msg.is_some());
        assert!(msg.unwrap().contains("evil.example.com"));
    }

    #[test]
    fn host_wildcard() {
        assert!(host_allowed("api.github.com", "*.github.com"));
        assert!(!host_allowed("evil.com", "*.github.com"));
    }
}
