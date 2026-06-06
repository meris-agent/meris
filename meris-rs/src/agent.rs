//! Native agent loop — P5-4 M1 (read-only tools + session persistence).

use crate::context::compress_messages;
use crate::permissions::check_tool_allowed;
use crate::provider::{chat_completions, resolve_config, ProviderConfig};
use crate::session::{load_session, new_session_id, now_iso, save_session, SessionRecord};
use crate::settings::load_settings;
use crate::tools::{run_builtin_tool, tool_schemas, BUILTIN_TOOL_NAMES, READONLY_TOOLS};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::Path;

const DEFAULT_MAX_MESSAGES: usize = 48;
const DEFAULT_MAX_TOOL_TOKENS: usize = 2000;

#[derive(Debug, Clone)]
pub struct AgentConfig {
    pub workspace: std::path::PathBuf,
    pub task: String,
    pub mode: String,
    pub max_turns: u32,
    pub session_id: Option<String>,
    pub resume: bool,
}

#[derive(Debug, Clone)]
pub struct AgentResult {
    pub lines: Vec<String>,
    pub session_id: String,
    pub status: String,
}

fn mode_read_only(mode: &str) -> bool {
    matches!(mode, "ask" | "plan" | "review")
}

fn system_prompt(mode: &str) -> String {
    format!(
        "You are Meris, a harness-first coding agent. Mode: {mode}. \
         Use read_file/glob/grep for exploration. Prefer tools over guessing."
    )
}

fn push_line(lines: &mut Vec<String>, line: impl Into<String>) {
    lines.push(line.into());
}

fn parse_tool_args(raw: &str) -> Value {
    serde_json::from_str(raw).unwrap_or_else(|_| json!({}))
}

fn execute_tool(
    workspace: &Path,
    tool: &str,
    args: &Value,
    settings: &HashMap<String, Value>,
    read_only: bool,
) -> String {
    if read_only && tool == "bash" {
        return "Error: bash not available in read-only mode".into();
    }
    if !BUILTIN_TOOL_NAMES.contains(&tool) {
        return format!(
            "Error: tool '{tool}' not available in native loop — use Python meris for full tools"
        );
    }
    if read_only && !READONLY_TOOLS.contains(&tool) {
        return format!("Error: tool '{tool}' not allowed in read-only mode");
    }
    run_builtin_tool(workspace, tool, args, settings)
}

pub fn run_agent(config: AgentConfig) -> Result<AgentResult, String> {
    let ws = config
        .workspace
        .canonicalize()
        .map_err(|e| format!("workspace: {e}"))?;
    let settings = load_settings(&ws);
    let read_only = mode_read_only(&config.mode);
    let provider_cfg: ProviderConfig = resolve_config(None, None)?;
    let tool_defs = tool_schemas(read_only);

    let mut lines: Vec<String> = Vec::new();
    let mut status = "running".to_string();

    let mut session = if config.resume {
        if let Some(sid) = &config.session_id {
            if let Some(rec) = load_session(&ws, sid)? {
                rec
            } else {
                return Err(format!("session not found: {sid}"));
            }
        } else {
            return Err("resume requires --session-id".into());
        }
    } else {
        let sid = config.session_id.clone().unwrap_or_else(new_session_id);
        SessionRecord {
            id: sid,
            task: config.task.clone(),
            mode: config.mode.clone(),
            status: "running".into(),
            created_at: now_iso(),
            updated_at: now_iso(),
            messages: vec![
                json!({"role": "system", "content": system_prompt(&config.mode)}),
                json!({"role": "user", "content": config.task}),
            ],
            turn: 0,
            max_turns: config.max_turns,
            workspace: ws.to_string_lossy().into(),
        }
    };

    push_line(
        &mut lines,
        format!("[meris] native loop session={} mode={}", session.id, session.mode),
    );

    let start_turn = session.turn;
    for turn_idx in start_turn..config.max_turns {
        session.turn = turn_idx + 1;
        session.status = "running".into();
        save_session(&ws, &mut session)?;

        let compressed =
            compress_messages(&session.messages, DEFAULT_MAX_MESSAGES, None, DEFAULT_MAX_TOOL_TOKENS);
        let assistant =
            chat_completions(&provider_cfg, &compressed, Some(&tool_defs), 120)?;

        if let Some(content) = assistant.get("content").and_then(|c| c.as_str()) {
            if !content.is_empty() {
                push_line(&mut lines, format!("\n[assistant]\n{content}"));
            }
        }

        let tool_calls = assistant
            .get("tool_calls")
            .and_then(|t| t.as_array())
            .cloned()
            .unwrap_or_default();

        if tool_calls.is_empty() {
            session.messages.push(assistant);
            status = "completed".into();
            session.status = status.clone();
            save_session(&ws, &mut session)?;
            break;
        }

        session.messages.push(assistant);

        for tc in &tool_calls {
            let name = tc
                .get("function")
                .and_then(|f| f.get("name"))
                .and_then(|n| n.as_str())
                .unwrap_or("");
            let args_raw = tc
                .get("function")
                .and_then(|f| f.get("arguments"))
                .and_then(|a| a.as_str())
                .unwrap_or("{}");
            let args = parse_tool_args(args_raw);
            let tc_id = tc.get("id").and_then(|i| i.as_str()).unwrap_or("");

            let result = if let Some(err) = check_tool_allowed(name, &args, &settings) {
                push_line(&mut lines, format!("\n[tool] {name} BLOCKED: {err}"));
                err
            } else {
                push_line(
                    &mut lines,
                    format!(
                        "\n[tool] {name}({})",
                        args_raw.chars().take(120).collect::<String>()
                    ),
                );
                execute_tool(&ws, name, &args, &settings, read_only)
            };

            session.messages.push(json!({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result,
            }));
        }
        save_session(&ws, &mut session)?;
    }

    if status == "running" {
        status = "max_turns".into();
        session.status = status.clone();
        let _ = save_session(&ws, &mut session);
        push_line(&mut lines, "[meris] max turns reached");
    }

    push_line(&mut lines, "\n[meris] done.");
    Ok(AgentResult {
        lines,
        session_id: session.id,
        status,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn read_only_modes() {
        assert!(mode_read_only("ask"));
        assert!(!mode_read_only("run"));
    }
}
