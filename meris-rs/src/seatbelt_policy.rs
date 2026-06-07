//! Meris-native macOS Seatbelt policy (programmatic SBPL — not Codex file copy).
//!
//! Design: preset-driven tiers aligned with G1/G2, generated at runtime.

use crate::sandbox::{
    collect_mask_paths, get_effective_network_mode, get_network_allowlist, get_sandbox_preset,
};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::Path;

/// Curated read roots for toolchain/runtime (narrower than Codex `(allow file-read*)`).
const MERIS_SYSTEM_READ_ROOTS: &[&str] = &[
    "/usr",
    "/bin",
    "/sbin",
    "/System",
    "/Library",
    "/private/etc",
    "/private/var/db",
    "/opt/homebrew",
];

const MERIS_TEMP_WRITE_ROOTS: &[&str] = &["/private/tmp", "/var/folders"];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MerisSeatbeltProfile {
    ReadOnly,
    WorkspaceWrite,
}

impl MerisSeatbeltProfile {
    pub fn id(self) -> &'static str {
        match self {
            Self::ReadOnly => "meris-read-only",
            Self::WorkspaceWrite => "meris-workspace-write",
        }
    }

    pub fn from_preset(preset: &str) -> Option<Self> {
        match preset {
            "read-only" => Some(Self::ReadOnly),
            "workspace-write" => Some(Self::WorkspaceWrite),
            _ => None,
        }
    }
}

#[derive(Debug, Clone)]
pub struct MerisSeatbeltPlan {
    pub profile: MerisSeatbeltProfile,
    pub policy: String,
    pub params: Vec<String>,
    pub network_enforcement: String,
}

fn push_process_essentials(out: &mut Vec<String>) {
    out.extend([
        "(version 1)".into(),
        "; Meris Seatbelt — programmatic profile (preset + network + masks)".into(),
        "(deny default)".into(),
        "(allow process-exec)".into(),
        "(allow process-fork)".into(),
        "(allow signal (target same-sandbox))".into(),
        "(allow process-info* (target same-sandbox))".into(),
        "(allow sysctl-read)".into(),
        "(allow mach-lookup)".into(),
        "(allow ipc-posix-sem)".into(),
        "(allow pseudo-tty)".into(),
        "(allow file-read* file-write* file-ioctl (literal \"/dev/ptmx\"))".into(),
        "(allow file-read* file-write* (regex #\"^/dev/ttys[0-9]+\"))".into(),
        "(allow file-ioctl (regex #\"^/dev/ttys[0-9]+\"))".into(),
        "(allow file-write-data (require-all (path \"/dev/null\") (vnode-type CHARACTER-DEVICE)))"
            .into(),
    ]);
}

fn push_read_tiers(out: &mut Vec<String>, params: &mut Vec<String>, workspace: &Path) {
    for root in MERIS_SYSTEM_READ_ROOTS {
        out.push(format!("(allow file-read* (subpath \"{root}\"))"));
    }
    out.push("(allow file-read* (subpath (param \"WORKSPACE\")))".into());
    params.push(format!("-DWORKSPACE={}", workspace.display()));
}

fn push_write_tiers(out: &mut Vec<String>, profile: MerisSeatbeltProfile) {
    match profile {
        MerisSeatbeltProfile::ReadOnly => {
            for root in MERIS_TEMP_WRITE_ROOTS {
                out.push(format!("(allow file-write* (subpath \"{root}\"))"));
            }
        }
        MerisSeatbeltProfile::WorkspaceWrite => {
            out.push("(allow file-write* (subpath (param \"WORKSPACE\")))".into());
            for root in MERIS_TEMP_WRITE_ROOTS {
                out.push(format!("(allow file-write* (subpath \"{root}\"))"));
            }
        }
    }
}

fn push_network_tier(out: &mut Vec<String>, settings: &HashMap<String, Value>) -> String {
    let mode = get_effective_network_mode(settings);
    match mode.as_str() {
        "isolated" => {
            out.push("(deny network*)".into());
            "deny-all".into()
        }
        "allowlist" => {
            // Meris hybrid: OS permits outbound; G2 command parser enforces host allowlist.
            out.push("(allow network-outbound)".into());
            let n = get_network_allowlist(settings).len();
            format!("allowlist-hybrid({n})")
        }
        _ => {
            out.push("(allow network-outbound)".into());
            "shared".into()
        }
    }
}

fn push_mask_tiers(
    out: &mut Vec<String>,
    params: &mut Vec<String>,
    workspace: &Path,
    settings: &HashMap<String, Value>,
) {
    for (i, mask) in collect_mask_paths(workspace, settings).iter().enumerate() {
        let canonical = mask
            .canonicalize()
            .unwrap_or_else(|_| mask.to_path_buf());
        out.push(format!(
            "(deny file-read* file-write* (subpath (param \"MASK_{i}\")))"
        ));
        params.push(format!("-DMASK_{i}={}", canonical.display()));
    }
}

/// Build Meris Seatbelt plan from harness settings.
pub fn plan_meris_seatbelt(
    workspace: &Path,
    settings: &HashMap<String, Value>,
) -> Result<MerisSeatbeltPlan, String> {
    let ws = workspace
        .canonicalize()
        .map_err(|e| format!("workspace: {e}"))?;
    let preset = get_sandbox_preset(settings);
    let profile = MerisSeatbeltProfile::from_preset(&preset).ok_or_else(|| {
        format!("seatbelt skipped for preset `{preset}` (danger-full-access uses osSandbox off)")
    })?;

    let mut lines: Vec<String> = Vec::new();
    let mut params: Vec<String> = Vec::new();
    push_process_essentials(&mut lines);
    push_read_tiers(&mut lines, &mut params, &ws);
    push_write_tiers(&mut lines, profile.clone());
    let network_enforcement = push_network_tier(&mut lines, settings);
    push_mask_tiers(&mut lines, &mut params, &ws, settings);

    Ok(MerisSeatbeltPlan {
        profile,
        policy: lines.join("\n"),
        params,
        network_enforcement,
    })
}

pub fn plan_to_json(plan: &MerisSeatbeltPlan) -> Value {
    json!({
        "profile": plan.profile.id(),
        "policySource": "meris-generated",
        "networkEnforcement": plan.network_enforcement,
        "policy": plan.policy,
        "params": plan.params,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::collections::HashMap;

    #[test]
    fn no_global_file_read_star() {
        let dir = tempfile::tempdir().unwrap();
        let mut settings = HashMap::new();
        settings.insert("sandbox".into(), json!({"preset": "workspace-write"}));
        let plan = plan_meris_seatbelt(dir.path(), &settings).unwrap();
        assert!(!plan.policy.contains("(allow file-read*)"));
        assert!(plan.policy.contains("/usr"));
        assert!(plan.policy.contains("WORKSPACE"));
    }

    #[test]
    fn read_only_uses_meris_profile() {
        let dir = tempfile::tempdir().unwrap();
        let mut settings = HashMap::new();
        settings.insert("sandbox".into(), json!({"preset": "read-only"}));
        let plan = plan_meris_seatbelt(dir.path(), &settings).unwrap();
        assert_eq!(plan.profile, MerisSeatbeltProfile::ReadOnly);
        assert!(!plan.policy.contains("(allow file-write* (subpath (param \"WORKSPACE\")))"));
        assert!(plan.policy.contains("/private/tmp"));
    }

    #[test]
    fn allowlist_hybrid_allows_outbound() {
        let dir = tempfile::tempdir().unwrap();
        let mut settings = HashMap::new();
        settings.insert(
            "sandbox".into(),
            json!({
                "preset": "workspace-write",
                "networkAllowlist": ["github.com"]
            }),
        );
        let plan = plan_meris_seatbelt(dir.path(), &settings).unwrap();
        assert!(plan.policy.contains("(allow network-outbound)"));
        assert!(!plan.policy.contains("(deny network*)"));
        assert!(plan.network_enforcement.starts_with("allowlist-hybrid"));
    }
}
