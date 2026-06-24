//! macOS Seatbelt execution via `sandbox-exec` (Meris G6.2+).

use super::{get_os_sandbox_mode, get_sandbox_preset, run_command_with_timeout};
use crate::seatbelt_policy::{plan_meris_seatbelt, plan_to_json, MerisSeatbeltProfile, MerisSeatbeltPlan};
use serde_json::Value;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

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

pub fn seatbelt_supported_preset(settings: &HashMap<String, Value>) -> bool {
    MerisSeatbeltProfile::from_preset(&get_sandbox_preset(settings)).is_some()
}

pub fn should_use_seatbelt(settings: &HashMap<String, Value>) -> Result<bool, String> {
    if !cfg!(target_os = "macos") {
        return Ok(false);
    }
    if !seatbelt_supported_preset(settings) {
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

pub fn build_seatbelt_policy(
    workspace: &Path,
    settings: &HashMap<String, Value>,
) -> Result<(String, Vec<String>), String> {
    let plan = plan_meris_seatbelt(workspace, settings)?;
    Ok((plan.policy, plan.params))
}

pub fn build_seatbelt_plan(
    workspace: &Path,
    settings: &HashMap<String, Value>,
) -> Result<MerisSeatbeltPlan, String> {
    plan_meris_seatbelt(workspace, settings)
}

pub fn seatbelt_plan_json(workspace: &Path, settings: &HashMap<String, Value>) -> Result<Value, String> {
    Ok(plan_to_json(&plan_meris_seatbelt(workspace, settings)?))
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
    let plan = plan_meris_seatbelt(workspace, settings)?;
    let mut cmd = Command::new(sandbox_exec);
    cmd.arg("-p").arg(plan.policy);
    for param in plan.params {
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
    fn workspace_write_plan_profile() {
        let dir = tempfile::tempdir().unwrap();
        let mut settings = HashMap::new();
        settings.insert(
            "sandbox".into(),
            json!({"preset": "workspace-write", "network": "isolated"}),
        );
        let plan = build_seatbelt_plan(dir.path(), &settings).unwrap();
        assert_eq!(plan.profile.id(), "meris-workspace-write");
        assert!(plan.policy.contains("(deny network*)"));
    }
}
