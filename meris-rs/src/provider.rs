//! OpenAI-compatible chat completions (P5-2).

use reqwest::blocking::Client;
use serde_json::{json, Value};
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
}
