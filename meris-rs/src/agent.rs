//! Native agent loop — P5-4 M1–M4.

use crate::context::compress_messages;
use crate::dod::handle_dod_failed;
use crate::events::{emit_submission, EventStream};
use crate::hooks::{record_ratchet_event, run_on_save_hook, run_post_hook, run_pre_hook};
use crate::mcp::{has_mcp_servers, is_mcp_tool, McpBridge};
use crate::permissions::check_tool_allowed;
use crate::plan::{extract_last_assistant_text, save_plan};
use crate::prompt::load_system_prompt;
use crate::provider::{chat_completions, chat_completions_stream, resolve_config, ProviderConfig};
use crate::sensors::{on_complete_enabled, run_on_complete_sensors, run_post_edit_sensors};
use crate::session::{load_session, new_session_id, now_iso, save_session, SessionRecord};
use crate::settings::load_settings;
use crate::tools::{
    run_builtin_tool, tool_needs_approval, tool_schemas, BUILTIN_TOOL_NAMES, EDIT_TOOLS,
    READONLY_TOOLS,
};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{self, BufRead, Write};
use std::path::{Path, PathBuf};

const DEFAULT_MAX_MESSAGES: usize = 48;
const DEFAULT_MAX_TOOL_TOKENS: usize = 2000;

#[derive(Debug, Clone)]
pub struct AgentConfig {
    pub workspace: PathBuf,
    pub task: String,
    pub mode: String,
    pub max_turns: u32,
    pub session_id: Option<String>,
    pub resume: bool,
    pub require_approval: bool,
    pub run_sensors_at_end: bool,
    pub event_stream: Option<PathBuf>,
    pub save_plan: bool,
    pub plan_output: Option<String>,
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

fn push_line(lines: &mut Vec<String>, line: impl Into<String>) {
    lines.push(line.into());
}

fn parse_tool_args(raw: &str) -> Value {
    serde_json::from_str(raw).unwrap_or_else(|_| json!({}))
}

fn file_change_preview(tool: &str, args: &Value) -> String {
    let path = args.get("path").and_then(|p| p.as_str()).unwrap_or("");
    if path.is_empty() {
        return String::new();
    }
    const MAX_LINES: usize = 20;
    if tool == "write_file" {
        let content = args.get("content").and_then(|c| c.as_str()).unwrap_or("");
        let mut body = format!("--- /dev/null\n+++ {path}\n@@ new file @@\n");
        for line in content.lines().take(MAX_LINES) {
            body.push_str(&format!("+{line}\n"));
        }
        let extra = content.lines().count().saturating_sub(MAX_LINES);
        if extra > 0 {
            body.push_str(&format!("… ({extra} more lines)\n"));
        }
        return body;
    }
    if tool == "edit_file" {
        let old = args.get("old_string").and_then(|c| c.as_str()).unwrap_or("");
        let new = args.get("new_string").and_then(|c| c.as_str()).unwrap_or("");
        let mut body = format!("--- {path}\n+++ {path}\n@@ edit @@\n");
        for line in old.lines().take(MAX_LINES) {
            body.push_str(&format!("-{line}\n"));
        }
        for line in new.lines().take(MAX_LINES) {
            body.push_str(&format!("+{line}\n"));
        }
        return body;
    }
    String::new()
}

fn ask_approval(tool: &str, args: &Value) -> bool {
    let req = json!({"tool": tool, "args": args});
    let Ok(payload) = serde_json::to_string(&req) else {
        return false;
    };
    println!("@meris-approve {payload}");
    let _ = io::stdout().flush();
    let stdin = io::stdin();
    let mut line = String::new();
    if stdin.lock().read_line(&mut line).is_err() {
        return false;
    }
    let v: Value = serde_json::from_str(line.trim()).unwrap_or(json!({}));
    v.get("approved").and_then(|b| b.as_bool()).unwrap_or(false)
}

fn needs_approval(name: &str, require: bool, mcp: Option<&McpBridge>) -> bool {
    if !require {
        return false;
    }
    if is_mcp_tool(name) {
        return mcp.map(|b| b.tool_needs_approval(name)).unwrap_or(false);
    }
    tool_needs_approval(name)
}

fn emit_event(
    events: &mut Option<EventStream>,
    kind: &str,
    message: &str,
    session: &str,
    turn: u32,
    extra: &[(&str, Value)],
) {
    if let Some(es) = events.as_mut() {
        let mut fields = HashMap::new();
        fields.insert("session".into(), json!(session));
        fields.insert("turn".into(), json!(turn));
        for (k, v) in extra {
            fields.insert((*k).into(), v.clone());
        }
        es.emit(kind, message, &fields);
    }
}

fn emit_token_chunks(
    events: &mut Option<EventStream>,
    content: &str,
    session: &str,
    turn: u32,
) {
    if content.is_empty() {
        return;
    }
    const CHUNK: usize = 320;
    let chars: Vec<char> = content.chars().collect();
    for (i, start) in (0..chars.len()).step_by(CHUNK).enumerate() {
        let end = (start + CHUNK).min(chars.len());
        let piece: String = chars[start..end].iter().collect();
        emit_event(
            events,
            "token",
            &piece,
            session,
            turn,
            &[("chunk", json!(i))],
        );
    }
}

fn run_builtin(
    workspace: &Path,
    tool: &str,
    args: &Value,
    settings: &HashMap<String, Value>,
    read_only: bool,
) -> String {
    if read_only && !READONLY_TOOLS.contains(&tool) {
        return format!("Error: tool '{tool}' not allowed in read-only mode");
    }
    if !BUILTIN_TOOL_NAMES.contains(&tool) {
        return format!("Error: tool '{tool}' not available in native loop");
    }
    run_builtin_tool(workspace, tool, args, settings)
}

fn run_tool(
    workspace: &Path,
    tool: &str,
    args: &Value,
    settings: &HashMap<String, Value>,
    read_only: bool,
    mcp: Option<&mut McpBridge>,
) -> String {
    if is_mcp_tool(tool) {
        let Some(bridge) = mcp else {
            return format!("Error: MCP tool '{tool}' but MCP bridge unavailable");
        };
        return bridge
            .call_tool(tool, args)
            .unwrap_or_else(|| format!("Error: MCP call failed for {tool}"));
    }
    run_builtin(workspace, tool, args, settings, read_only)
}

fn apply_post_edit(
    workspace: &Path,
    settings: &HashMap<String, Value>,
    tool: &str,
    result: &str,
    lines: &mut Vec<String>,
    events: &mut Option<EventStream>,
    session_id: &str,
) -> String {
    if !EDIT_TOOLS.contains(&tool) {
        return result.to_string();
    }
    let (ok, sensor_out) = run_post_edit_sensors(workspace, settings);
    if sensor_out.is_empty() {
        return result.to_string();
    }
    let tag = if ok { "PASS" } else { "FAIL" };
    push_line(
        lines,
        format!(
            "\n[sensor] postEdit {tag}\n{}",
            sensor_out.chars().take(1500).collect::<String>()
        ),
    );
    if let Some(es) = events.as_mut() {
        let mut fields = HashMap::new();
        fields.insert("session".into(), json!(session_id));
        fields.insert("ok".into(), json!(ok));
        es.emit("sensor", &sensor_out.chars().take(500).collect::<String>(), &fields);
    }
    if ok {
        result.to_string()
    } else {
        format!(
            "{result}\n\n[postEdit sensor FAIL]\n{}",
            sensor_out.chars().take(2000).collect::<String>()
        )
    }
}

fn run_pre_hooks(
    workspace: &Path,
    tool: &str,
    args: &Value,
    lines: &mut Vec<String>,
) -> Option<String> {
    let pre = run_pre_hook(workspace, tool, args)?;
    if pre.block {
        push_line(
            lines,
            format!("\n[tool] {tool} HOOK BLOCK: {}", pre.message),
        );
        return Some(pre.message);
    }
    if !pre.message.is_empty() {
        push_line(
            lines,
            format!(
                "\n[hook] pre: {}",
                pre.message.chars().take(500).collect::<String>()
            ),
        );
    }
    None
}

fn run_post_hooks(
    workspace: &Path,
    tool: &str,
    args: &Value,
    result: &str,
    lines: &mut Vec<String>,
) -> Option<String> {
    let post = run_post_hook(workspace, tool, args, result)?;
    if post.block {
        push_line(lines, format!("\n[tool] {tool} HOOK BLOCK (post): {}", post.message));
        return Some(post.message);
    }
    if !post.message.is_empty() {
        push_line(
            lines,
            format!(
                "\n[hook] post: {}",
                post.message.chars().take(500).collect::<String>()
            ),
        );
    }
    None
}

fn run_on_save(
    workspace: &Path,
    tool: &str,
    args: &Value,
    result: &str,
    lines: &mut Vec<String>,
) -> String {
    if !EDIT_TOOLS.contains(&tool) {
        return result.to_string();
    }
    let Some(rel) = args.get("path").and_then(|p| p.as_str()) else {
        return result.to_string();
    };
    let Some(hr) = run_on_save_hook(workspace, rel) else {
        return result.to_string();
    };
    if !hr.message.is_empty() {
        push_line(
            lines,
            format!(
                "\n[hook] onSave: {}",
                hr.message.chars().take(500).collect::<String>()
            ),
        );
    }
    if hr.block {
        return format!("{result}\n[onSave hook BLOCKED]\n{}", hr.message);
    }
    result.to_string()
}

pub fn run_agent(config: AgentConfig) -> Result<AgentResult, String> {
    let ws = config
        .workspace
        .canonicalize()
        .map_err(|e| format!("workspace: {e}"))?;
    let settings = load_settings(&ws);
    let read_only = mode_read_only(&config.mode);
    let provider_cfg: ProviderConfig = resolve_config(None, None)?;

    let mut tool_defs = tool_schemas(read_only);
    let mut mcp_bridge = if has_mcp_servers(&settings) {
        McpBridge::start(&ws)
    } else {
        None
    };
    if let Some(bridge) = mcp_bridge.as_mut() {
        if let Some(mcp_schemas) = bridge.load_schemas(read_only) {
            tool_defs.extend(mcp_schemas);
        }
    }

    let mut events = config
        .event_stream
        .as_ref()
        .map(|p| EventStream::open(p))
        .transpose()?;

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
                json!({"role": "system", "content": load_system_prompt(&ws, &config.mode)}),
                json!({"role": "user", "content": config.task}),
            ],
            turn: 0,
            max_turns: config.max_turns,
            workspace: ws.to_string_lossy().into(),
        }
    };

    emit_submission(
        &mut events,
        "user",
        &config.task,
        &session.id,
    );

    push_line(
        &mut lines,
        format!("[meris] native loop session={} mode={}", session.id, session.mode),
    );
    emit_event(
        &mut events,
        "session_start",
        &format!("[meris] native loop session={} mode={}", session.id, session.mode),
        &session.id,
        session.turn,
        &[("mode", json!(config.mode)), ("model", json!(provider_cfg.model))],
    );

    if let Some(bridge) = mcp_bridge.as_ref() {
        for note in &bridge.notes {
            push_line(&mut lines, format!("[mcp] {note}"));
        }
    }

    let start_turn = session.turn;
    for turn_idx in start_turn..config.max_turns {
        session.turn = turn_idx + 1;
        session.status = "running".into();
        save_session(&ws, &mut session)?;

        let before_len = session.messages.len();
        let compressed = compress_messages(
            &session.messages,
            DEFAULT_MAX_MESSAGES,
            None,
            DEFAULT_MAX_TOOL_TOKENS,
        );
        if compressed.len() < before_len {
            let note = format!(
                "context compressed {before_len} → {} messages",
                compressed.len()
            );
            push_line(&mut lines, format!("[meris] {note}"));
            emit_event(
                &mut events,
                "thinking",
                &note,
                &session.id,
                session.turn,
                &[],
            );
        }
        let assistant = if events.is_some() {
            chat_completions_stream(
                &provider_cfg,
                &compressed,
                Some(&tool_defs),
                120,
                &mut events,
                &session.id,
                session.turn,
            )?
        } else {
            chat_completions(&provider_cfg, &compressed, Some(&tool_defs), 120)?
        };

        if events.is_none() {
            if let Some(content) = assistant.get("content").and_then(|c| c.as_str()) {
                if !content.is_empty() {
                    push_line(&mut lines, format!("\n[assistant]\n{content}"));
                    emit_token_chunks(&mut events, content, &session.id, session.turn);
                }
            }
        } else if let Some(content) = assistant.get("content").and_then(|c| c.as_str()) {
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

            emit_event(
                &mut events,
                "tool_start",
                name,
                &session.id,
                session.turn,
                &[("tool", json!(name)), ("args", args.clone())],
            );

            let mcp_ref = mcp_bridge.as_ref();
            let mut result = if let Some(err) = check_tool_allowed(name, &args, &settings) {
                push_line(&mut lines, format!("\n[tool] {name} BLOCKED: {err}"));
                record_ratchet_event(
                    &ws,
                    "permission_denied",
                    &session.id,
                    &config.task,
                    &err,
                    name,
                );
                err
            } else if let Some(blocked) = run_pre_hooks(&ws, name, &args, &mut lines) {
                blocked
            } else if needs_approval(name, config.require_approval, mcp_ref) {
                if !ask_approval(name, &args) {
                    push_line(&mut lines, format!("\n[tool] {name} DENIED by user"));
                    "User denied tool execution".into()
                } else {
                    push_line(
                        &mut lines,
                        format!(
                            "\n[tool] {name}({})",
                            args_raw.chars().take(120).collect::<String>()
                        ),
                    );
                    let out = run_tool(
                        &ws,
                        name,
                        &args,
                        &settings,
                        read_only,
                        mcp_bridge.as_mut(),
                    );
                    let out = run_on_save(&ws, name, &args, &out, &mut lines);
                    apply_post_edit(
                        &ws,
                        &settings,
                        name,
                        &out,
                        &mut lines,
                        &mut events,
                        &session.id,
                    )
                }
            } else {
                push_line(
                    &mut lines,
                    format!(
                        "\n[tool] {name}({})",
                        args_raw.chars().take(120).collect::<String>()
                    ),
                );
                let out = run_tool(
                    &ws,
                    name,
                    &args,
                    &settings,
                    read_only,
                    mcp_bridge.as_mut(),
                );
                let out = run_on_save(&ws, name, &args, &out, &mut lines);
                apply_post_edit(
                    &ws,
                    &settings,
                    name,
                    &out,
                    &mut lines,
                    &mut events,
                    &session.id,
                )
            };

            if let Some(blocked) = run_post_hooks(&ws, name, &args, &result, &mut lines) {
                result = blocked;
            }

            if (name == "write_file" || name == "edit_file") {
                if let Some(path) = args.get("path").and_then(|p| p.as_str()) {
                let preview = file_change_preview(name, &args);
                emit_event(
                    &mut events,
                    "file_change",
                    path,
                    &session.id,
                    session.turn,
                    &[
                        ("tool", json!(name)),
                        ("path", json!(path)),
                        ("diff_preview", json!(preview)),
                    ],
                );
                }
            }

            emit_event(
                &mut events,
                "tool_end",
                &result.chars().take(2000).collect::<String>(),
                &session.id,
                session.turn,
                &[("tool", json!(name))],
            );

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

    if config.mode == "plan" && config.save_plan && status == "completed" {
        if let Some(text) = extract_last_assistant_text(&session.messages) {
            let out_ref = config.plan_output.as_deref();
            match save_plan(&ws, &text, out_ref) {
                Ok(path) => {
                    push_line(&mut lines, format!("[meris] plan saved: {}", path.display()));
                }
                Err(e) => push_line(&mut lines, format!("[meris] plan save failed: {e}")),
            }
        }
    }

    if config.mode == "run"
        && config.run_sensors_at_end
        && on_complete_enabled(&settings)
        && (status == "completed" || status == "max_turns")
    {
        if let Some((ok, out)) = run_on_complete_sensors(&ws) {
            push_line(
                &mut lines,
                format!(
                    "\n[sensor] DoD {}\n{}",
                    if ok { "PASS" } else { "FAIL" },
                    out.chars().take(2000).collect::<String>()
                ),
            );
            if let Some(es) = events.as_mut() {
                let mut fields = HashMap::new();
                fields.insert("session".into(), json!(session.id));
                fields.insert("ok".into(), json!(ok));
                es.emit("sensor", &out.chars().take(500).collect::<String>(), &fields);
            }
            if !ok {
                status = "dod_failed".into();
                session.status = status.clone();
                let _ = save_session(&ws, &mut session);
                for hint in handle_dod_failed(&ws, &session.id, &config.task, &config.mode, &out) {
                    push_line(&mut lines, hint);
                }
            }
        }
    }

    if let Some(es) = events.as_mut() {
        let mut fields = HashMap::new();
        fields.insert("session".into(), json!(session.id));
        fields.insert("mode".into(), json!(config.mode));
        fields.insert("status".into(), json!(status));
        es.emit("done", "", &fields);
    }

    if let Some(bridge) = mcp_bridge {
        bridge.close();
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
