//! OpenAI-compatible chat completions (P5-2).

use crate::events::EventStream;
use futures_util::StreamExt;
use reqwest::blocking::Client;
use reqwest::Client as AsyncClient;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::time::Duration;

const DEFAULT_BASE: &str = "https://api.openai.com/v1";
const DEFAULT_MODEL: &str = "gpt-4o-mini";

#[derive(Debug, Clone)]
pub struct ProviderConfig {
    pub api_key: String,
    pub base_url: String,
    pub model: String,
}

#[derive(Debug, Clone)]
pub struct ProviderProbe {
    pub api_key_set: bool,
    pub base_url: String,
    pub model: String,
}

pub fn resolve_api_key() -> Option<String> {
    for name in [
        "MERIS_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "LLM_API_KEY",
    ] {
        if let Ok(v) = std::env::var(name) {
            let t = v.trim();
            if !t.is_empty() && t != "not-needed" {
                return Some(t.to_string());
            }
        }
    }
    None
}

pub fn resolve_base_url(explicit: Option<&str>) -> String {
    if let Some(u) = explicit {
        let t = u.trim();
        if !t.is_empty() {
            return normalize_base_url(t);
        }
    }
    for name in ["MERIS_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL", "DEEPSEEK_BASE_URL"] {
        if let Ok(v) = std::env::var(name) {
            let t = v.trim();
            if !t.is_empty() {
                return normalize_base_url(t);
            }
        }
    }
    DEFAULT_BASE.to_string()
}

pub fn resolve_model(explicit: Option<&str>) -> String {
    if let Some(m) = explicit {
        let t = m.trim();
        if !t.is_empty() {
            return t.to_string();
        }
    }
    for name in ["MERIS_MODEL", "LLM_MODEL", "OPENAI_MODEL", "DEEPSEEK_MODEL"] {
        if let Ok(v) = std::env::var(name) {
            let t = v.trim();
            if !t.is_empty() {
                return t.to_string();
            }
        }
    }
    DEFAULT_MODEL.to_string()
}

fn normalize_base_url(url: &str) -> String {
    let u = url.trim().trim_end_matches('/');
    if u.ends_with("/v1") {
        u.to_string()
    } else {
        format!("{u}/v1")
    }
}

pub fn resolve_config(base_url: Option<&str>, model: Option<&str>) -> Result<ProviderConfig, String> {
    let api_key = resolve_api_key().ok_or_else(|| {
        "API key not set — use OPENAI_API_KEY, DEEPSEEK_API_KEY, or MERIS_API_KEY".to_string()
    })?;
    Ok(ProviderConfig {
        api_key,
        base_url: resolve_base_url(base_url),
        model: resolve_model(model),
    })
}

pub fn probe_provider(base_url: Option<&str>, model: Option<&str>) -> ProviderProbe {
    ProviderProbe {
        api_key_set: resolve_api_key().is_some(),
        base_url: resolve_base_url(base_url),
        model: resolve_model(model),
    }
}

pub fn build_chat_body(
    cfg: &ProviderConfig,
    messages: &[Value],
    tools: Option<&[Value]>,
) -> Value {
    let mut body = json!({
        "model": cfg.model,
        "messages": messages,
    });
    if let Some(tools) = tools {
        if !tools.is_empty() {
            if let Some(obj) = body.as_object_mut() {
                obj.insert("tools".into(), json!(tools));
                obj.insert("tool_choice".into(), json!("auto"));
            }
        }
    }
    body
}

pub fn parse_assistant_message(resp: &Value) -> Result<Value, String> {
    let choice = resp
        .get("choices")
        .and_then(|c| c.as_array())
        .and_then(|a| a.first())
        .ok_or_else(|| "missing choices[0] in API response".to_string())?;
    let message = choice
        .get("message")
        .ok_or_else(|| "missing message in API response".to_string())?;
    let content = message
        .get("content")
        .and_then(|c| c.as_str())
        .unwrap_or("");
    let mut out = json!({
        "role": "assistant",
        "content": content,
    });
    if let Some(tcs) = message.get("tool_calls") {
        if let Some(arr) = tcs.as_array() {
            if !arr.is_empty() {
                out["tool_calls"] = json!(arr);
            }
        }
    }
    Ok(out)
}

pub fn chat_completions(
    cfg: &ProviderConfig,
    messages: &[Value],
    tools: Option<&[Value]>,
    timeout_secs: u64,
) -> Result<Value, String> {
    let client = Client::builder()
        .timeout(Duration::from_secs(timeout_secs.clamp(10, 600)))
        .build()
        .map_err(|e| format!("http client: {e}"))?;
    let url = format!("{}/chat/completions", cfg.base_url.trim_end_matches('/'));
    let body = build_chat_body(cfg, messages, tools);
    let resp = client
        .post(&url)
        .bearer_auth(&cfg.api_key)
        .json(&body)
        .send()
        .map_err(|e| format!("request: {e}"))?;
    let status = resp.status();
    let text = resp.text().map_err(|e| format!("read body: {e}"))?;
    if !status.is_success() {
        return Err(format!("HTTP {status}: {}", text.chars().take(400).collect::<String>()));
    }
    let data: Value = serde_json::from_str(&text).map_err(|e| format!("json: {e}"))?;
    parse_assistant_message(&data)
}

fn merge_tool_call_delta(tool_calls: &mut HashMap<usize, Value>, delta_tcs: &Value) {
    let Some(arr) = delta_tcs.as_array() else {
        return;
    };
    for tc in arr {
        let idx = tc.get("index").and_then(|i| i.as_u64()).unwrap_or(0) as usize;
        let entry = tool_calls
            .entry(idx)
            .or_insert_with(|| {
                json!({
                    "id": "",
                    "type": "function",
                    "function": { "name": "", "arguments": "" }
                })
            });
        if let Some(id) = tc.get("id").and_then(|i| i.as_str()) {
            entry["id"] = json!(id);
        }
        if let Some(func) = tc.get("function") {
            if let Some(name) = func.get("name").and_then(|n| n.as_str()) {
                let cur = entry["function"]["name"].as_str().unwrap_or("");
                entry["function"]["name"] = json!(format!("{cur}{name}"));
            }
            if let Some(args) = func.get("arguments").and_then(|a| a.as_str()) {
                let cur = entry["function"]["arguments"].as_str().unwrap_or("");
                entry["function"]["arguments"] = json!(format!("{cur}{args}"));
            }
        }
    }
}

fn build_assistant_from_stream(
    content_parts: &[String],
    reasoning_parts: &[String],
    tool_calls: &HashMap<usize, Value>,
) -> Value {
    let content = content_parts.join("");
    let mut out = json!({
        "role": "assistant",
        "content": content,
    });
    if !reasoning_parts.is_empty() {
        out["reasoning_content"] = json!(reasoning_parts.join(""));
    }
    if !tool_calls.is_empty() {
        let mut keys: Vec<_> = tool_calls.keys().copied().collect();
        keys.sort_unstable();
        let ordered: Vec<Value> = keys.iter().map(|k| tool_calls[k].clone()).collect();
        out["tool_calls"] = json!(ordered);
    }
    out
}

/// Process one SSE `data:` payload; returns true when stream is done.
pub fn process_sse_chat_chunk(
    data: &str,
    content_parts: &mut Vec<String>,
    reasoning_parts: &mut Vec<String>,
    tool_calls: &mut HashMap<usize, Value>,
    events: &mut Option<EventStream>,
    session: &str,
    turn: u32,
    token_chunk: &mut u32,
    reasoning_chunk: &mut u32,
) -> bool {
    let trimmed = data.trim();
    if trimmed.is_empty() || trimmed == "[DONE]" {
        return trimmed == "[DONE]";
    }
    let Ok(json) = serde_json::from_str::<Value>(trimmed) else {
        return false;
    };
    let Some(delta) = json
        .get("choices")
        .and_then(|c| c.as_array())
        .and_then(|a| a.first())
        .and_then(|c| c.get("delta"))
    else {
        return false;
    };

    if let Some(reasoning) = delta
        .get("reasoning_content")
        .and_then(|r| r.as_str())
        .filter(|s| !s.is_empty())
    {
        reasoning_parts.push(reasoning.to_string());
        if let Some(es) = events.as_mut() {
            let mut fields = HashMap::new();
            fields.insert("session".into(), json!(session));
            fields.insert("turn".into(), json!(turn));
            fields.insert("chunk".into(), json!(*reasoning_chunk));
            es.emit("reasoning", reasoning, &fields);
            *reasoning_chunk += 1;
        }
    }

    if let Some(content) = delta
        .get("content")
        .and_then(|c| c.as_str())
        .filter(|s| !s.is_empty())
    {
        content_parts.push(content.to_string());
        if let Some(es) = events.as_mut() {
            let mut fields = HashMap::new();
            fields.insert("session".into(), json!(session));
            fields.insert("turn".into(), json!(turn));
            fields.insert("chunk".into(), json!(*token_chunk));
            es.emit("token", content, &fields);
            *token_chunk += 1;
        }
    }

    if let Some(tcs) = delta.get("tool_calls") {
        merge_tool_call_delta(tool_calls, tcs);
    }
    false
}

async fn chat_completions_stream_async(
    cfg: &ProviderConfig,
    messages: &[Value],
    tools: Option<&[Value]>,
    timeout_secs: u64,
    events: &mut Option<EventStream>,
    session: &str,
    turn: u32,
) -> Result<Value, String> {
    let client = AsyncClient::builder()
        .timeout(Duration::from_secs(timeout_secs.clamp(10, 600)))
        .build()
        .map_err(|e| format!("http client: {e}"))?;
    let url = format!("{}/chat/completions", cfg.base_url.trim_end_matches('/'));
    let mut body = build_chat_body(cfg, messages, tools);
    if let Some(obj) = body.as_object_mut() {
        obj.insert("stream".into(), json!(true));
    }

    let response = client
        .post(&url)
        .bearer_auth(&cfg.api_key)
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("request: {e}"))?;
    let status = response.status();
    if !status.is_success() {
        let text = response
            .text()
            .await
            .unwrap_or_else(|_| "(no body)".into());
        return Err(format!(
            "HTTP {status}: {}",
            text.chars().take(400).collect::<String>()
        ));
    }

    let mut stream = response.bytes_stream();
    let mut buffer = String::new();
    let mut content_parts: Vec<String> = Vec::new();
    let mut reasoning_parts: Vec<String> = Vec::new();
    let mut tool_calls: HashMap<usize, Value> = HashMap::new();
    let mut token_chunk = 0u32;
    let mut reasoning_chunk = 0u32;

    while let Some(chunk) = stream.next().await {
        let bytes = chunk.map_err(|e| format!("stream read: {e}"))?;
        buffer.push_str(&String::from_utf8_lossy(&bytes));
        while let Some(pos) = buffer.find('\n') {
            let line: String = buffer.drain(..=pos).collect();
            let line = line.trim();
            if let Some(data) = line.strip_prefix("data:") {
                let done = process_sse_chat_chunk(
                    data,
                    &mut content_parts,
                    &mut reasoning_parts,
                    &mut tool_calls,
                    events,
                    session,
                    turn,
                    &mut token_chunk,
                    &mut reasoning_chunk,
                );
                if done {
                    return Ok(build_assistant_from_stream(
                        &content_parts,
                        &reasoning_parts,
                        &tool_calls,
                    ));
                }
            }
        }
    }

    Ok(build_assistant_from_stream(
        &content_parts,
        &reasoning_parts,
        &tool_calls,
    ))
}

/// OpenAI-compatible SSE streaming; emits live `token` / `reasoning` events when `events` is set.
pub fn chat_completions_stream(
    cfg: &ProviderConfig,
    messages: &[Value],
    tools: Option<&[Value]>,
    timeout_secs: u64,
    events: &mut Option<EventStream>,
    session: &str,
    turn: u32,
) -> Result<Value, String> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| format!("tokio runtime: {e}"))?;
    rt.block_on(chat_completions_stream_async(
        cfg,
        messages,
        tools,
        timeout_secs,
        events,
        session,
        turn,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_base_adds_v1() {
        assert_eq!(
            normalize_base_url("https://api.deepseek.com"),
            "https://api.deepseek.com/v1"
        );
        assert_eq!(
            normalize_base_url("https://api.openai.com/v1"),
            "https://api.openai.com/v1"
        );
    }

    #[test]
    fn parse_assistant_text() {
        let resp = json!({
            "choices": [{
                "message": { "role": "assistant", "content": "pong" }
            }]
        });
        let msg = parse_assistant_message(&resp).unwrap();
        assert_eq!(msg["content"], "pong");
    }

    #[test]
    fn build_chat_with_tools() {
        let cfg = ProviderConfig {
            api_key: "k".into(),
            base_url: DEFAULT_BASE.into(),
            model: "m".into(),
        };
        let body = build_chat_body(
            &cfg,
            &[json!({"role": "user", "content": "hi"})],
            Some(&[json!({"type": "function", "function": {"name": "read_file"}})]),
        );
        assert!(body.get("tools").is_some());
    }

    #[test]
    fn process_sse_token_delta() {
        let data = r#"{"choices":[{"delta":{"content":"hi"}}]}"#;
        let mut content = Vec::new();
        let mut reasoning = Vec::new();
        let mut tools = HashMap::new();
        let mut token_chunk = 0u32;
        let mut reasoning_chunk = 0u32;
        let done = process_sse_chat_chunk(
            data,
            &mut content,
            &mut reasoning,
            &mut tools,
            &mut None,
            "sess",
            1,
            &mut token_chunk,
            &mut reasoning_chunk,
        );
        assert!(!done);
        assert_eq!(content, vec!["hi".to_string()]);
        assert_eq!(token_chunk, 0);
    }

    #[test]
    fn process_sse_reasoning_delta() {
        let data = r#"{"choices":[{"delta":{"reasoning_content":"think"}}]}"#;
        let mut content = Vec::new();
        let mut reasoning = Vec::new();
        let mut tools = HashMap::new();
        let mut token_chunk = 0u32;
        let mut reasoning_chunk = 0u32;
        process_sse_chat_chunk(
            data,
            &mut content,
            &mut reasoning,
            &mut tools,
            &mut None,
            "sess",
            1,
            &mut token_chunk,
            &mut reasoning_chunk,
        );
        assert_eq!(reasoning, vec!["think".to_string()]);
    }
}
