//! macOS Seatbelt sandbox via `sandbox-exec` (Phase G6.2).

use super::{
    collect_mask_paths, get_effective_network_mode, get_os_sandbox_mode, get_sandbox_preset,
    run_command_with_timeout,
};
use serde_json::Value;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

const BASE_POLICY: &str = include_str!("../seatbelt/base_policy.sbpl");

#[cfg(target_os = "macos")]
pub fn find_sandbox_exec() -> Option<PathBuf> {
    for candidate in ["/usr/bin/sandbox-exec", "/bin/sandbox-exec"] {
        let path = PathBuf::from(candidate);
        if path.is_file() {
            return Some(path);
        }
    }
    std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths).find_map(|dir| {
            let p = dir.join("sandbox-exec");
            p.is_file().then_some(p)
        })
    })
}

#[cfg(not(target_os = "macos"))]
pub fn find_sandbox_exec() -> Option<PathBuf> {
    None
}

pub fn should_use_seatbelt(settings: &HashMap<String, Value>) -> Result<bool, String> {
    if !cfg!(target_os = "macos") {
        return Ok(false);
    }
    match get_os_sandbox_mode(settings).as_str() {
        "off" => Ok(false),
        "require" => {
            if find_sandbox_exec().is_some() {
                Ok(true)
            } else {
                Err("sandbox.osSandbox=require but sandbox-exec not found on PATH".into())
            }
        }
        "auto" | _ => Ok(find_sandbox_exec().is_some()),
    }
}

/// Build SBPL policy and `-D` template args for sandbox-exec.
pub fn build_seatbelt_policy(
    workspace: &Path,
    settings: &HashMap<String, Value>,
) -> Result<(String, Vec<String>), String> {
    let ws = workspace
        .canonicalize()
        .map_err(|e| format!("workspace: {e}"))?;
    let mut policy = BASE_POLICY.to_string();
    let mut params: Vec<String> = Vec::new();

    if get_effective_network_mode(settings) == "isolated" {
        policy.push_str("\n(deny network*)\n");
    }

    for (i, mask) in collect_mask_paths(&ws, settings).iter().enumerate() {
        let canonical = mask
            .canonicalize()
            .unwrap_or_else(|_| mask.to_path_buf());
        policy.push_str(&format!(
            "\n(deny file-read* file-write* (subpath (param \"MASK_{i}\")))\n"
        ));
        params.push(format!("-DMASK_{i}={}", canonical.display()));
    }

    let preset = get_sandbox_preset(settings);
    if preset == "workspace-write" {
        policy.push_str("\n(allow file-write* (subpath (param \"WRITABLE_ROOT_0\")))\n");
        params.push(format!("-DWRITABLE_ROOT_0={}", ws.display()));
        policy.push_str("\n(allow file-write* (subpath \"/private/tmp\"))\n");
        policy.push_str("\n(allow file-write* (subpath \"/var/folders\"))\n");
    }

    Ok((policy, params))
}

pub fn build_seatbelt_command(
    workspace: &Path,
    command: &str,
    settings: &HashMap<String, Value>,
) -> Result<Command, String> {
    let sandbox_exec = find_sandbox_exec().ok_or_else(|| "sandbox-exec not found".to_string())?;
    let ws = workspace
        .canonicalize()
        .map_err(|e| format!("workspace: {e}"))?;
    let (policy, params) = build_seatbelt_policy(workspace, settings)?;
    let mut cmd = Command::new(sandbox_exec);
    cmd.arg("-p").arg(policy);
    for param in params {
        cmd.arg(param);
    }
    cmd.arg("--").arg("sh").arg("-c").arg(command);
    cmd.current_dir(&ws);
    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
    Ok(cmd)
}

pub fn run_bash_seatbelt(
    workspace: &Path,
    command: &str,
    timeout_secs: u64,
    settings: &HashMap<String, Value>,
) -> Result<(i32, String), String> {
    let cmd = build_seatbelt_command(workspace, command, settings)?;
    run_command_with_timeout(cmd, timeout_secs)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::collections::HashMap;

    #[test]
    fn policy_includes_network_deny_when_isolated() {
        let dir = tempfile::tempdir().unwrap();
        let mut settings = HashMap::new();
        settings.insert("sandbox".into(), json!({"network": "isolated"}));
        let (policy, _) = build_seatbelt_policy(dir.path(), &settings).unwrap();
        assert!(policy.contains("(deny network*)"));
    }

    #[test]
    fn workspace_write_adds_writable_root() {
        let dir = tempfile::tempdir().unwrap();
        let mut settings = HashMap::new();
        settings.insert(
            "sandbox".into(),
            json!({"preset": "workspace-write", "network": "shared"}),
        );
        let (policy, params) = build_seatbelt_policy(dir.path(), &settings).unwrap();
        assert!(policy.contains("WRITABLE_ROOT_0"));
        assert!(params.iter().any(|p| p.starts_with("-DWRITABLE_ROOT_0=")));
    }

    #[test]
    fn read_only_has_no_writable_root_param() {
        let dir = tempfile::tempdir().unwrap();
        let mut settings = HashMap::new();
        settings.insert("sandbox".into(), json!({"preset": "read-only"}));
        let (policy, params) = build_seatbelt_policy(dir.path(), &settings).unwrap();
        assert!(!policy.contains("WRITABLE_ROOT_0"));
        assert!(params.iter().all(|p| !p.starts_with("-DWRITABLE_ROOT_0=")));
    }
}
