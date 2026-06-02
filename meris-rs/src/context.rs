//! Token estimation and message compression (parity with meris.harness.context).

use serde_json::{json, Value};

const CHARS_PER_TOKEN: usize = 4;

pub fn estimate_tokens(text: &str) -> usize {
    if text.is_empty() {
        return 0;
    }
    std::cmp::max(1, text.len() / CHARS_PER_TOKEN)
}

pub fn estimate_messages_tokens(messages: &[Value]) -> usize {
    let mut total = 0usize;
    for m in messages {
        let content = m.get("content").and_then(|c| c.as_str()).unwrap_or("");
        total += estimate_tokens(content);
        if let Some(tcs) = m.get("tool_calls") {
            if let Ok(s) = serde_json::to_string(tcs) {
                total += estimate_tokens(&s);
            }
        }
    }
    total
}

pub fn truncate_content(text: &str, max_tokens: usize) -> String {
    let budget_chars = max_tokens * CHARS_PER_TOKEN;
    if text.len() <= budget_chars {
        return text.to_string();
    }
    let keep = budget_chars.saturating_sub(40);
    let truncated: String = text.chars().take(keep).collect();
    format!("{truncated}\n...[meris: truncated for token budget]")
}

pub fn shrink_tool_results(messages: &[Value], max_tool_tokens: usize) -> Vec<Value> {
    messages
        .iter()
        .map(|m| {
            if m.get("role").and_then(|r| r.as_str()) == Some("tool") {
                let content = m.get("content").and_then(|c| c.as_str()).unwrap_or("");
                if estimate_tokens(content) > max_tool_tokens {
                    let mut copy = m.clone();
                    if let Some(obj) = copy.as_object_mut() {
                        obj.insert(
                            "content".into(),
                            json!(truncate_content(content, max_tool_tokens)),
                        );
                    }
                    return copy;
                }
            }
            m.clone()
        })
        .collect()
}

pub fn compress_messages(
    messages: &[Value],
    max_messages: usize,
    max_tokens: Option<usize>,
    max_tool_tokens: usize,
) -> Vec<Value> {
    let mut msgs = shrink_tool_results(messages, max_tool_tokens);

    if let Some(limit) = max_tokens {
        if estimate_messages_tokens(&msgs) > limit {
            msgs = compress_by_tokens(&msgs, limit);
        }
    }

    if msgs.len() <= max_messages {
        return sanitize_messages_for_api(&msgs);
    }

    let system: Vec<Value> = msgs
        .iter()
        .filter(|m| m.get("role").and_then(|r| r.as_str()) == Some("system"))
        .cloned()
        .collect();
    let rest: Vec<Value> = msgs
        .iter()
        .filter(|m| m.get("role").and_then(|r| r.as_str()) != Some("system"))
        .cloned()
        .collect();

    if rest.is_empty() {
        return msgs;
    }

    let first_user = rest
        .iter()
        .position(|m| m.get("role").and_then(|r| r.as_str()) == Some("user"))
        .unwrap_or(0);
    let head: Vec<Value> = rest[..=first_user].to_vec();
    let mut budget = max_messages
        .saturating_sub(system.len())
        .saturating_sub(head.len())
        .saturating_sub(1);
    if budget < 4 {
        budget = 4;
    }
    let tail_start = rest.len().saturating_sub(budget);
    let tail: Vec<Value> = if budget > 0 && tail_start > first_user + 1 {
        rest[tail_start..].to_vec()
    } else {
        vec![]
    };

    let dropped = rest.len().saturating_sub(head.len() + tail.len());
    let marker = json!({
        "role": "system",
        "content": format!("[meris] Context compressed: dropped {dropped} older messages."),
    });

    let mut out = system;
    out.extend(head);
    out.push(marker);
    out.extend(tail);
    sanitize_messages_for_api(&out)
}

fn drop_incomplete_tool_round(messages: &[Value]) -> Vec<Value> {
    let mut out: Vec<Value> = messages.to_vec();
    while out.last().and_then(|m| m.get("role")).and_then(|r| r.as_str()) == Some("tool") {
        out.pop();
    }
    if out.last().map(|m| {
        m.get("role").and_then(|r| r.as_str()) == Some("assistant")
            && m.get("tool_calls").is_some()
    }) == Some(true)
    {
        out.pop();
    }
    out
}

pub fn sanitize_messages_for_api(messages: &[Value]) -> Vec<Value> {
    let mut out: Vec<Value> = vec![];
    let mut pending: std::collections::HashSet<String> = std::collections::HashSet::new();

    for m in messages {
        if m.get("role").and_then(|r| r.as_str()) == Some("tool") {
            if let Some(tid) = m.get("tool_call_id").and_then(|t| t.as_str()) {
                if pending.remove(tid) {
                    out.push(m.clone());
                }
            }
            continue;
        }

        if !pending.is_empty() {
            out = drop_incomplete_tool_round(&out);
            pending.clear();
        }

        out.push(m.clone());

        if m.get("role").and_then(|r| r.as_str()) == Some("assistant") {
            pending.clear();
            if let Some(tcs) = m.get("tool_calls").and_then(|v| v.as_array()) {
                for tc in tcs {
                    if let Some(id) = tc.get("id").and_then(|v| v.as_str()) {
                        pending.insert(id.to_string());
                    }
                }
            }
        }
    }

    if !pending.is_empty() {
        out = drop_incomplete_tool_round(&out);
    }
    out
}

fn compress_by_tokens(messages: &[Value], max_tokens: usize) -> Vec<Value> {
    let system: Vec<Value> = messages
        .iter()
        .filter(|m| m.get("role").and_then(|r| r.as_str()) == Some("system"))
        .cloned()
        .collect();
    let rest: Vec<Value> = messages
        .iter()
        .filter(|m| m.get("role").and_then(|r| r.as_str()) != Some("system"))
        .cloned()
        .collect();

    if rest.is_empty() {
        return messages.to_vec();
    }

    let first_user_idx = rest
        .iter()
        .position(|m| m.get("role").and_then(|r| r.as_str()) == Some("user"))
        .unwrap_or(0);
    let head: Vec<Value> = rest[..=first_user_idx].to_vec();
    let mut fixed = system.clone();
    fixed.extend(head.clone());
    let fixed_tokens = estimate_messages_tokens(&fixed);
    let marker_tokens = estimate_tokens("[meris] token budget marker");
    let mut budget = max_tokens.saturating_sub(fixed_tokens + marker_tokens);
    if budget < 500 {
        budget = 500;
    }

    let mut tail: Vec<Value> = vec![];
    let mut used = 0usize;
    for m in rest[first_user_idx + 1..].iter().rev() {
        let t = estimate_messages_tokens(std::slice::from_ref(m));
        if used + t > budget && !tail.is_empty() {
            break;
        }
        tail.insert(0, m.clone());
        used += t;
    }

    let marker = json!({
        "role": "system",
        "content": format!(
            "[meris] Token budget: kept ~{} tokens (limit {max_tokens}), dropped older turns.",
            fixed_tokens + used
        ),
    });

    fixed.push(marker);
    fixed.extend(tail);
    sanitize_messages_for_api(&fixed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn estimate_tokens_basic() {
        assert_eq!(estimate_tokens(""), 0);
        assert!(estimate_tokens("abcd") >= 1);
    }

    #[test]
    fn compress_by_token_budget() {
        let mut msgs = vec![json!({"role": "system", "content": "sys"})];
        msgs.push(json!({"role": "user", "content": "original task"}));
        for _ in 0..30 {
            msgs.push(json!({"role": "assistant", "content": "a".repeat(500)}));
            msgs.push(json!({"role": "user", "content": "u".repeat(500)}));
        }
        let out = compress_messages(&msgs, 100, Some(3000), 2000);
        assert!(estimate_messages_tokens(&out) <= 3500);
        assert!(out.iter().any(|m| {
            m.get("role").and_then(|r| r.as_str()) == Some("user")
                && m.get("content")
                    .and_then(|c| c.as_str())
                    .unwrap_or("")
                    .contains("original")
        }));
    }
}
