//! Meris native core — mirrors Python harness primitives for fast startup paths.

pub mod agent;
pub mod context;
pub mod dod;
pub mod events;
pub mod hooks;
pub mod mcp;
pub mod permissions;
pub mod plan;
pub mod prompt;
pub mod provider;
pub mod review;
pub mod seatbelt_policy;
pub mod sandbox;
pub mod sensors;
pub mod run_entry;
pub mod session;
pub mod settings;
pub mod tools;

pub use agent::{run_agent, AgentConfig, AgentResult};
pub use events::{emit_submission, EventStream};
pub use hooks::{has_tool_hooks, record_ratchet_event, run_on_save_hook, run_post_hook, run_pre_hook, HookResult};
pub use plan::{extract_last_assistant_text, save_plan};
pub use prompt::{fallback_system_prompt, load_system_prompt};
pub use review::load_review_task;
pub use dod::handle_dod_failed;
pub use run_entry::{
    native_loop_enabled_for_run_entry, parse_direct_run_args, should_inject_native_loop_auto,
    DirectRunArgs,
};
pub use mcp::{has_mcp_servers, is_mcp_tool, McpBridge};
pub use context::{compress_messages, estimate_messages_tokens, estimate_tokens};
pub use permissions::check_tool_allowed;
pub use provider::{
    chat_completions, probe_provider, resolve_config, build_chat_body, parse_assistant_message,
    ProviderConfig, ProviderProbe,
};
pub use sandbox::{
    check_bash_sandbox, collect_mask_paths, find_bubblewrap, find_sandbox_exec, get_bash_timeout,
    get_mask_secrets, get_network_mode, get_os_sandbox_mode, get_sandbox_mode, os_sandbox_probe,
    os_sandbox_probe_workspace, run_bash_in_workspace, scan_bash_command, seatbelt_plan_json,
    should_use_bubblewrap, should_use_seatbelt, verdict_to_json, SandboxVerdict,
};
pub use sensors::{
    on_complete_enabled, post_edit_commands, run_on_complete_sensors, run_post_edit_sensors,
    run_shell_commands,
};
pub use session::{list_sessions, load_session, new_session_id, save_session, SessionRecord};
pub use settings::load_settings;
pub use tools::{
    run_builtin_tool, run_readonly_tool, tool_needs_approval, tool_schemas, tool_schemas_json,
    BUILTIN_TOOL_NAMES, EDIT_TOOLS, READONLY_TOOLS,
};
