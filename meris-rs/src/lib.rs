//! Meris native core — mirrors Python harness primitives for fast startup paths.

pub mod context;
pub mod permissions;
pub mod sandbox;
pub mod settings;

pub use context::{compress_messages, estimate_messages_tokens, estimate_tokens};
pub use permissions::check_tool_allowed;
pub use sandbox::{
    check_bash_sandbox, collect_mask_paths, find_bubblewrap, get_bash_timeout, get_mask_secrets,
    get_network_mode, get_os_sandbox_mode, get_sandbox_mode, os_sandbox_probe,
    os_sandbox_probe_workspace, run_bash_in_workspace, scan_bash_command, should_use_bubblewrap,
    verdict_to_json, SandboxVerdict,
};
pub use settings::load_settings;
